from django.conf import settings
from django.db import models


class ApprovalRule(models.Model):
    """Approval matrix row-set: invoices whose total falls in [min_amount, max_amount] use this rule."""
    name = models.CharField(max_length=100)
    min_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    max_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)  # null = no cap
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["min_amount"]

    def __str__(self):
        return self.name


class ApprovalStep(models.Model):
    """Steps with the SAME stage number run in parallel; stages run one after another."""
    rule = models.ForeignKey(ApprovalRule, on_delete=models.CASCADE, related_name="steps")
    stage = models.PositiveIntegerField(default=1)
    role = models.CharField(max_length=20)
    sla_hours = models.PositiveIntegerField(default=24)
    escalation_role = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["rule_id", "stage", "id"]


class ApprovalTask(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        ESCALATED = "ESCALATED", "Escalated"
        CANCELLED = "CANCELLED", "Cancelled"

    invoice = models.ForeignKey("invoices.Invoice", on_delete=models.CASCADE, related_name="approval_tasks")
    step = models.ForeignKey(ApprovalStep, null=True, on_delete=models.SET_NULL)
    stage = models.PositiveIntegerField(default=1)
    role = models.CharField(max_length=20)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    due_at = models.DateTimeField()
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    escalated = models.BooleanField(default=False)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    decided_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["invoice_id", "stage", "id"]
