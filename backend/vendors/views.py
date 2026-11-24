from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts import audit
from accounts.permissions import roles_required
from .models import Vendor, VendorBank
from .serializers import VendorSerializer, VendorBankSerializer
from .gst import validate_gstin


class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.prefetch_related("banks")
    serializer_class = VendorSerializer
    filterset_fields = ["status"]

    def get_queryset(self):
        qs = super().get_queryset()
        s = self.request.query_params.get("status")
        q = self.request.query_params.get("q")
        if s:
            qs = qs.filter(status=s)
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

    def perform_create(self, serializer):
        v = serializer.save(created_by=self.request.user)
        audit.log(self.request.user, "VENDOR_CREATED", "Vendor", v.id, name=v.name)

    @action(detail=False, methods=["post"], url_path="validate-gstin")
    def check_gstin(self, request):
        ok, msg = validate_gstin(request.data.get("gstin", ""))
        return Response({"valid": ok, "message": msg})

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Onboarding step 1: clerk submits vendor for approval (needs a bank account + GSTIN)."""
        v = self.get_object()
        if not v.gstin or not v.banks.exists():
            return Response({"detail": "GSTIN and at least one bank account are required"}, status=400)
        v.status = Vendor.Status.PENDING_APPROVAL
        v.save(update_fields=["status"])
        audit.log(request.user, "VENDOR_SUBMITTED", "Vendor", v.id)
        audit.notify("Vendor awaiting approval", v.name, "/vendors", role="MANAGER")
        return Response(VendorSerializer(v).data)

    @action(detail=True, methods=["post"], permission_classes=[roles_required("MANAGER", "FINANCE_HEAD", "CFO")])
    def decide(self, request, pk=None):
        """Onboarding step 2: manager approves/rejects. Approval also marks bank accounts verified."""
        v = self.get_object()
        approve = bool(request.data.get("approve"))
        v.status = Vendor.Status.ACTIVE if approve else Vendor.Status.REJECTED
        v.onboarding_comment = request.data.get("comment", "")
        v.approved_by = request.user
        v.save()
        if approve:
            v.banks.update(is_verified=True)
        audit.log(request.user, "VENDOR_APPROVED" if approve else "VENDOR_REJECTED", "Vendor", v.id,
                  comment=v.onboarding_comment)
        return Response(VendorSerializer(v).data)


class VendorBankViewSet(viewsets.ModelViewSet):
    queryset = VendorBank.objects.all()
    serializer_class = VendorBankSerializer

    def perform_create(self, serializer):
        b = serializer.save()
        audit.log(self.request.user, "BANK_ADDED", "Vendor", b.vendor_id, bank=str(b))

    def perform_update(self, serializer):
        # Bank detail changes must be re-verified (fraud control).
        b = serializer.save(is_verified=False)
        audit.log(self.request.user, "BANK_CHANGED", "Vendor", b.vendor_id, bank=str(b))
