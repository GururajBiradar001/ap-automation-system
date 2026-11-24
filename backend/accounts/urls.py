from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("users", views.UserViewSet, basename="user")
router.register("audit-logs", views.AuditLogViewSet, basename="auditlog")
router.register("notifications", views.NotificationViewSet, basename="notification")

urlpatterns = [
    path("auth/login/", views.login),
    path("auth/me/", views.me),
    path("", include(router.urls)),
]
