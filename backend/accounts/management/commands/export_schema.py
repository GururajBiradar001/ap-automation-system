"""Writes the PostgreSQL DDL for all AP tables (no database connection needed).
   python manage.py export_schema ../docs/schema.sql
"""
import re
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.backends.postgresql.base import DatabaseWrapper

APPS = ("accounts", "vendors", "purchasing", "invoices", "workflow", "payments", "authtoken")
SKIP = re.compile(r"accounts_user_groups|accounts_user_user_permissions|auth_group|auth_permission")


def split_top(s):
    parts, depth, cur = [], 0, ""
    for ch in s:
        depth += (ch == "(") - (ch == ")")
        if ch == "," and depth == 0:
            parts.append(cur.strip()); cur = ""
        else:
            cur += ch
    return parts + [cur.strip()]


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("outfile")

    def handle(self, *a, **o):
        cfg = connections.configure_settings({"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "ap"}})["default"]
        conn = DatabaseWrapper(cfg, alias="pg")
        models = [m for m in apps.get_models(include_auto_created=True) if m._meta.app_label in APPS and not m._meta.proxy]
        done, ordered = set(), []

        def visit(m):
            if m in done:
                return
            done.add(m)
            for f in m._meta.local_fields:
                r = f.remote_field.model if f.remote_field else None
                if r in models and r is not m:
                    visit(r)
            ordered.append(m)
        for m in models:
            visit(m)
        with conn.schema_editor(collect_sql=True, atomic=False) as se:
            for m in ordered:
                se.create_model(m)
        creates, alters = [], []
        for stmt in se.collected_sql:
            stmt = stmt.strip().rstrip(";")
            if SKIP.search(stmt):
                continue
            m = re.match(r'CREATE TABLE ("[^"]+") \((.*)\)$', stmt, re.S)
            if m:
                creates.append(f"CREATE TABLE {m.group(1)} (\n  " + ",\n  ".join(split_top(m.group(2))) + "\n);\n")
            else:
                alters.append(stmt + ";")
        head = ["-- AP Automation - PostgreSQL schema (generated from the Django models).",
                "-- `python manage.py migrate` creates exactly these tables. Table name = <app>_<model>.", ""]
        open(o["outfile"], "w").write("\n".join(head + creates + ["-- Foreign keys & indexes"] + alters) + "\n")
        self.stdout.write(f"{len(creates)} tables, {len(alters)} constraints/indexes -> {o['outfile']}")
