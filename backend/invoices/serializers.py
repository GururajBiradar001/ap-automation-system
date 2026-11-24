from rest_framework import serializers
from .models import Invoice, InvoiceLine, ValidationIssue


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = ["id", "line_no", "item_code", "description", "quantity", "unit_price", "gst_rate",
                  "amount", "po_line"]
        read_only_fields = ["po_line"]


class IssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ValidationIssue
        fields = ["id", "category", "severity", "message"]


class InvoiceListSerializer(serializers.ModelSerializer):
    vendor_name = serializers.SerializerMethodField()
    issue_count = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = ["id", "original_filename", "invoice_number", "invoice_date", "due_date", "vendor",
                  "vendor_name", "po_number", "total_amount", "status", "source", "ocr_confidence",
                  "ocr_accuracy", "issue_count", "received_at"]

    def get_vendor_name(self, o):
        return o.vendor.name if o.vendor_id else o.vendor_name_raw

    def get_issue_count(self, o):
        return o.issues.filter(severity="ERROR").count()


class InvoiceDetailSerializer(InvoiceListSerializer):
    lines = InvoiceLineSerializer(many=True, required=False)
    issues = IssueSerializer(many=True, read_only=True)
    file_url = serializers.SerializerMethodField()
    approvals = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()

    class Meta(InvoiceListSerializer.Meta):
        fields = InvoiceListSerializer.Meta.fields + [
            "vendor_name_raw", "vendor_gstin", "currency", "subtotal", "cgst", "sgst", "igst",
            "purchase_order", "match_type_used", "page_count", "ocr_engine", "extracted_snapshot",
            "lines", "issues", "file_url", "approvals", "payment", "approved_at", "paid_at"]
        read_only_fields = ["status", "purchase_order", "match_type_used", "page_count", "ocr_engine",
                            "extracted_snapshot", "approved_at", "paid_at", "source"]

    def get_file_url(self, o):
        req = self.context.get("request")
        return req.build_absolute_uri(o.file.url) if req and o.file else None

    def get_approvals(self, o):
        return [{"id": t.id, "stage": t.stage, "role": t.role, "status": t.status, "due_at": t.due_at,
                 "decided_by": t.decided_by.username if t.decided_by else None, "decided_at": t.decided_at,
                 "comment": t.comment, "escalated": t.escalated} for t in o.approval_tasks.all()]

    def get_payment(self, o):
        p = o.payments.order_by("-id").first()
        return {"id": p.id, "ref": p.payment_ref, "status": p.status, "bank_reference": p.bank_reference} if p else None

    def update(self, inst, validated):
        lines = validated.pop("lines", None)
        for k, v in validated.items():
            setattr(inst, k, v)
        inst.save()
        if lines is not None:
            inst.lines.all().delete()
            for i, l in enumerate(lines, 1):
                l.pop("line_no", None)
                InvoiceLine.objects.create(invoice=inst, line_no=i, **l)
        return inst
