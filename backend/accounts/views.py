from django.db.models import Q
from rest_framework import viewsets, mixins
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import authenticate

from .models import User, AuditLog, Notification
from .serializers import UserSerializer, AuditLogSerializer, NotificationSerializer
from .permissions import roles_required
from . import audit


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    user = authenticate(username=request.data.get("username"), password=request.data.get("password"))
    if not user:
        return Response({"detail": "Invalid credentials"}, status=400)
    token, _ = Token.objects.get_or_create(user=user)
    audit.log(user, "LOGIN", "User", user.id)
    return Response({"token": token.key, "user": UserSerializer(user).data})


@api_view(["GET"])
def me(request):
    return Response(UserSerializer(request.user).data)


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all().order_by("username")
    serializer_class = UserSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [roles_required("MANAGER", "FINANCE_HEAD", "CFO")]

    def get_queryset(self):
        qs = AuditLog.objects.select_related("user")
        p = self.request.query_params
        if p.get("entity_type"):
            qs = qs.filter(entity_type=p["entity_type"])
        if p.get("entity_id"):
            qs = qs.filter(entity_id=p["entity_id"])
        return qs


class NotificationViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        u = self.request.user
        return Notification.objects.filter(Q(user=u) | Q(role=u.role))
