from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models


class User(AbstractUser):
    """Custom user with a role - drives role-based approvals and permissions."""
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        AP_CLERK = "AP_CLERK", "AP Clerk"
        MANAGER = "MANAGER", "Manager"
        FINANCE_HEAD = "FINANCE_HEAD", "Finance Head"
        CFO = "CFO", "CFO"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.AP_CLERK)

    def has_role(self, *roles):
        return self.is_superuser or self.role in roles


class AuditLog(models.Model):
    """Immutable trail of every important action (Reports -> Audit logs)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="audit_logs")
    action = models.CharField(max_length=60)
    entity_type = models.CharField(max_length=40)
    entity_id = models.CharField(max_length=40, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class Notification(models.Model):
    """In-app notification (reminders, escalations, assignments)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.CASCADE, related_name="notifications")
    role = models.CharField(max_length=20, blank=True)   # role-wide broadcast
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
