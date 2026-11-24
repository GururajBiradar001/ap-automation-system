from rest_framework import serializers
from .models import User, AuditLog, Notification


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "role"]


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", default="system", read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "user_name", "action", "entity_type", "entity_id", "details", "created_at"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "body", "link", "is_read", "created_at"]
