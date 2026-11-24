from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from accounts import audit
from accounts.permissions import roles_required
from .models import Invoice
from .serializers import InvoiceListSerializer, InvoiceDetailSerializer
from .services import pipeline


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related("vendor").prefetch_related("lines", "issues")
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_class(self):
        return InvoiceListSerializer if self.action == "list" else InvoiceDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("vendor"):
            qs = qs.filter(vendor_id=p["vendor"])
        if p.get("q"):
            q = p["q"]
            qs = qs.filter(invoice_number__icontains=q) | qs.filter(vendor_name_raw__icontains=q) \
                | qs.filter(vendor__name__icontains=q)
        return qs

    def create(self, request, *a, **kw):
        return Response({"detail": "Use POST /api/invoices/upload/"}, status=405)

    @action(detail=False, methods=["post"])
    def upload(self, request):
        """Drag & drop / bulk upload: send one or many files under the key 'files'."""
        files = request.FILES.getlist("files") or request.FILES.getlist("file")
        if not files:
            return Response({"detail": "No files received"}, status=400)
        results = []
        for f in files:
            try:
                inv = pipeline.create_invoice(f, request.user)
                results.append({"filename": f.name, "id": inv.id, "status": inv.status,
                                "invoice_number": inv.invoice_number})
            except Exception as e:                      # one bad file must not kill the batch
                results.append({"filename": f.name, "error": str(e)})
        return Response({"results": results}, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *a, **kw):
        inv = self.get_object()
        if inv.status not in ("EXCEPTION", "RECEIVED"):
            return Response({"detail": "Only invoices in exception can be edited"}, status=400)
        resp = super().partial_update(request, *a, **kw)
        audit.log(request.user, "INVOICE_CORRECTED", "Invoice", inv.pk, fields=list(request.data.keys()))
        return resp

    @action(detail=True, methods=["post"])
    def revalidate(self, request, pk=None):
        """After a clerk corrects data: re-run validation + matching (+ approval start if clean)."""
        inv = self.get_object()
        if inv.status not in ("EXCEPTION", "RECEIVED"):
            return Response({"detail": "Invoice is already in workflow"}, status=400)
        pipeline.evaluate(inv, request.user)
        inv.refresh_from_db()
        return Response(InvoiceDetailSerializer(inv, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="force-submit",
            permission_classes=[roles_required("MANAGER", "FINANCE_HEAD", "CFO")])
    def force_submit(self, request, pk=None):
        """Manager override: push an exception invoice into approval with a logged justification."""
        inv = self.get_object()
        comment = request.data.get("comment", "").strip()
        if not comment:
            return Response({"detail": "A justification comment is required"}, status=400)
        if inv.status != "EXCEPTION":
            return Response({"detail": "Only exception invoices can be overridden"}, status=400)
        audit.log(request.user, "VALIDATION_OVERRIDDEN", "Invoice", inv.pk, comment=comment,
                  errors=[i.message for i in inv.issues.filter(severity="ERROR")])
        inv.ocr_accuracy = pipeline.compute_accuracy(inv)
        inv.save(update_fields=["ocr_accuracy"])
        from workflow import engine
        engine.start_approval(inv, request.user)
        inv.refresh_from_db()
        return Response(InvoiceDetailSerializer(inv, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        inv = self.get_object()
        if inv.status in ("PAID", "PAYMENT_REQUESTED", "APPROVED"):
            return Response({"detail": "Cannot reject after approval"}, status=400)
        inv.status = Invoice.Status.REJECTED
        inv.save(update_fields=["status"])
        inv.approval_tasks.filter(status="PENDING").update(status="CANCELLED")
        audit.log(request.user, "INVOICE_REJECTED", "Invoice", inv.pk, comment=request.data.get("comment", ""))
        return Response({"status": inv.status})
