"""Email ingestion: pull invoice attachments from an IMAP mailbox (or a local .eml file for testing).

  python manage.py ingest_emails                    # reads IMAP_HOST / IMAP_USER / IMAP_PASSWORD
  python manage.py ingest_emails --eml sample.eml   # offline test
Schedule with cron / Celery beat in production.
"""
import email
import imaplib
import os
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from invoices.services import pipeline


class Command(BaseCommand):
    help = "Ingest invoice attachments from email"

    def add_arguments(self, parser):
        parser.add_argument("--eml", help="Path to a local .eml file (offline test)")

    def handle(self, *args, **opts):
        if opts["eml"]:
            with open(opts["eml"], "rb") as fh:
                self._process(email.message_from_bytes(fh.read()))
            return
        host, user, pwd = (os.getenv("IMAP_HOST"), os.getenv("IMAP_USER"), os.getenv("IMAP_PASSWORD"))
        if not (host and user and pwd):
            self.stderr.write("Set IMAP_HOST, IMAP_USER and IMAP_PASSWORD in .env")
            return
        box = imaplib.IMAP4_SSL(host)
        box.login(user, pwd)
        box.select("INBOX")
        _, ids = box.search(None, "UNSEEN")
        for num in ids[0].split():
            _, data = box.fetch(num, "(RFC822)")
            self._process(email.message_from_bytes(data[0][1]))
        box.logout()

    def _process(self, msg):
        sender = msg.get("From", "")
        for part in msg.walk():
            fn = part.get_filename()
            if fn and fn.lower().endswith(pipeline.ALLOWED_EXT):
                f = ContentFile(part.get_payload(decode=True), name=fn)
                inv = pipeline.create_invoice(f, None, source="EMAIL")
                self.stdout.write(f"Ingested {fn} from {sender} -> invoice #{inv.pk} [{inv.status}]")
