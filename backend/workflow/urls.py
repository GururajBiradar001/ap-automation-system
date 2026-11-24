from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("approval-rules", views.ApprovalRuleViewSet, basename="approvalrule")
router.register("approval-tasks", views.ApprovalTaskViewSet, basename="approvaltask")
urlpatterns = [
    path("workflow/run-escalations/", views.run_escalations),
    path("", include(router.urls)),
]
