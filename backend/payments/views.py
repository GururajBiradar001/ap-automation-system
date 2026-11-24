from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import roles_required
from .advice import build_advice_pdf
from .models import Payment
from .serializers import PaymentSerializer
from .services import release_payment


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Payment.objects.select_related("vendor", "invoice", "bank")
    serializer_class = PaymentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        s = self.request.query_params.get("status")
        return qs.filter(status=s) if s else qs

    @action(detail=True, methods=["post"], permission_classes=[roles_required("FINANCE_HEAD", "CFO")])
    def release(self, request, pk=None):
        try:
            p = release_payment(self.get_object(), request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(PaymentSerializer(p).data)

    @action(detail=True, methods=["get"])
    def advice(self, request, pk=None):
        p = self.get_object()
        resp = HttpResponse(build_advice_pdf(p), content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="advice-{p.payment_ref}.pdf"'
        return resp
