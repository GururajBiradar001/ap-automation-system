from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import roles_required
from . import engine
from .models import ApprovalRule, ApprovalTask
from .serializers import ApprovalRuleSerializer, ApprovalTaskSerializer


class ApprovalRuleViewSet(viewsets.ModelViewSet):
    """Configurable approval matrix (admin / finance head)."""
    queryset = ApprovalRule.objects.prefetch_related("steps")
    serializer_class = ApprovalRuleSerializer
    permission_classes = [roles_required("FINANCE_HEAD", "CFO")]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return super().get_permissions()


class ApprovalTaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ApprovalTaskSerializer

    def get_queryset(self):
        qs = ApprovalTask.objects.select_related("invoice", "invoice__vendor")
        u, p = self.request.user, self.request.query_params
        if p.get("mine", "1") == "1" and not u.is_superuser and u.role != "ADMIN":
            qs = qs.filter(role=u.role)
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        return qs

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        task = self.get_object()
        try:
            engine.decide(task, request.user, bool(request.data.get("approve")), request.data.get("comment", ""))
        except PermissionError as e:
            return Response({"detail": str(e)}, status=403)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        task.refresh_from_db()
        return Response(ApprovalTaskSerializer(task).data)


@api_view(["POST"])
@permission_classes([roles_required("MANAGER", "FINANCE_HEAD", "CFO")])
def run_escalations(request):
    """Manual trigger for the escalation/reminder job (normally run by cron)."""
    return Response(engine.run_escalations())
