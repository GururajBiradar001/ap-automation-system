from .models import AuditLog, Notification, User


def log(user, action, entity_type, entity_id="", **details):
    AuditLog.objects.create(
        user=user if (user and getattr(user, "pk", None)) else None,
        action=action, entity_type=entity_type, entity_id=str(entity_id), details=details)


def notify(title, body="", link="", user=None, role=""):
    Notification.objects.create(user=user, role=role, title=title, body=body, link=link)
