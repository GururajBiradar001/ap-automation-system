"""Approval engine: matrix lookup, staged/parallel tasks, decisions, escalation, reminders."""
from datetime import timedelta
from types import SimpleNamespace
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts import audit
from .models import ApprovalRule, ApprovalStep, ApprovalTask

DEFAULT_STEPS = [(1, "MANAGER", 24, "FINANCE_HEAD")]


def pick_rule(amount):
    qs = ApprovalRule.objects.filter(is_active=True, min_amount__lte=amount or 0)
    qs = qs.filter(Q(max_amount__isnull=True) | Q(max_amount__gte=amount or 0))
    return qs.order_by("-min_amount").first()


def _create_stage(invoice, stage):
    rule = pick_rule(invoice.total_amount)
    steps = list(rule.steps.filter(stage=stage)) if rule else []
    if not rule:                                    # fallback when matrix is not configured
        steps = [SimpleNamespace(id=None, stage=s, role=r, sla_hours=h, escalation_role=e)
                 for s, r, h, e in DEFAULT_STEPS if s == stage]
    now = timezone.now()
    for s in steps:
        ApprovalTask.objects.create(
            invoice=invoice, step_id=s.id, stage=s.stage, role=s.role,
            due_at=now + timedelta(hours=s.sla_hours))
        audit.notify(f"Approval needed: invoice {invoice.invoice_number or invoice.pk}",
                     f"Amount {invoice.total_amount}", f"/invoices/{invoice.pk}", role=s.role)
    return len(steps)


def _max_stage(invoice):
    rule = pick_rule(invoice.total_amount)
    if not rule:
        return max(s for s, *_ in DEFAULT_STEPS)
    return max((s.stage for s in rule.steps.all()), default=1)


def start_approval(invoice, user=None):
    invoice.approval_tasks.filter(status="PENDING").update(status="CANCELLED")
    invoice.status = "PENDING_APPROVAL"
    invoice.save(update_fields=["status"])
    n = _create_stage(invoice, 1)
    rule = pick_rule(invoice.total_amount)
    audit.log(user, "APPROVAL_STARTED", "Invoice", invoice.pk, rule=rule.name if rule else "default", tasks=n)
    return n


@transaction.atomic
def decide(task, user, approve, comment=""):
    """Role-based decision. Returns the invoice."""
    if task.status != "PENDING":
        raise ValueError("Task is no longer pending")
    if not user.has_role(task.role, "ADMIN"):
        raise PermissionError(f"This task needs the {task.role} role")
    inv = task.invoice
    task.status = "APPROVED" if approve else "REJECTED"
    task.decided_by, task.decided_at, task.comment = user, timezone.now(), comment
    task.save()
    audit.log(user, "APPROVED" if approve else "REJECTED", "Invoice", inv.pk,
              stage=task.stage, role=task.role, comment=comment)
    if not approve:
        inv.approval_tasks.filter(status="PENDING").update(status="CANCELLED")
        inv.status = "REJECTED"
        inv.save(update_fields=["status"])
        return inv
    # Stage complete only when ALL parallel tasks of the stage are approved
    if inv.approval_tasks.filter(stage=task.stage, status="PENDING").exists():
        return inv
    if task.stage < _max_stage(inv):
        _create_stage(inv, task.stage + 1)
        return inv
    inv.status = "APPROVED"
    inv.approved_at = timezone.now()
    inv.save(update_fields=["status", "approved_at"])
    audit.log(user, "FULLY_APPROVED", "Invoice", inv.pk)
    from payments.services import create_payment_request
    create_payment_request(inv, user)
    return inv


def run_escalations(now=None):
    """Send reminders and escalate overdue tasks. Run via cron / `manage.py process_escalations`."""
    now = now or timezone.now()
    reminded = escalated = 0
    for t in ApprovalTask.objects.filter(status="PENDING").select_related("invoice", "step"):
        total = (t.due_at - t.created_at).total_seconds() or 1
        left = (t.due_at - now).total_seconds()
        if left <= 0:
            esc_role = t.step.escalation_role if t.step else "FINANCE_HEAD"
            if esc_role and esc_role != t.role:
                t.status = "ESCALATED"
                t.save(update_fields=["status"])
                hrs = t.step.sla_hours if t.step else 24
                ApprovalTask.objects.create(invoice=t.invoice, step=t.step, stage=t.stage, role=esc_role,
                                            due_at=now + timedelta(hours=hrs), escalated=True)
                audit.log(None, "ESCALATED", "Invoice", t.invoice_id, from_role=t.role, to_role=esc_role)
                audit.notify(f"ESCALATED: invoice {t.invoice.invoice_number or t.invoice_id}",
                             f"Overdue with {t.role}", f"/invoices/{t.invoice_id}", role=esc_role)
                escalated += 1
        elif left / total <= 0.25 and not t.reminder_sent_at:
            audit.notify(f"Reminder: approval due soon ({t.invoice.invoice_number or t.invoice_id})",
                         f"Due {t.due_at:%d %b %H:%M}", f"/invoices/{t.invoice_id}", role=t.role)
            t.reminder_sent_at = now
            t.save(update_fields=["reminder_sent_at"])
            reminded += 1
    return {"reminded": reminded, "escalated": escalated}
