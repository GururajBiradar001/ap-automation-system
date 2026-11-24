from django.conf import settings
from django.db import models


def invoice_upload_path(instance, filename):
    return f"invoices/{filename}"


class Invoice(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Received"
        EXCEPTION = "EXCEPTION", "Exception (needs review)"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        PAYMENT_REQUESTED = "PAYMENT_REQUESTED", "Payment requested"
        PAID = "PAID", "Paid"

    class Source(models.TextChoices):
        UPLOAD = "UPLOAD", "Upload"
        EMAIL = "EMAIL", "Email"

    file = models.FileField(upload_to=invoice_upload_path)
    original_filename = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64, db_index=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.UPLOAD)
    page_count = models.PositiveIntegerField(default=1)

    # --- extracted / editable header fields ---
    vendor = models.ForeignKey("vendors.Vendor", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="invoices")
    vendor_name_raw = models.CharField(max_length=255, blank=True)
    vendor_gstin = models.CharField(max_length=15, blank=True)
    invoice_number = models.CharField(max_length=60, blank=True, db_index=True)
    invoice_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    po_number = models.CharField(max_length=40, blank=True)
    purchase_order = models.ForeignKey("purchasing.PurchaseOrder", null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name="invoices")
    currency = models.CharField(max_length=3, default="INR")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    cgst = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    match_type_used = models.CharField(max_length=10, blank=True)

    # --- OCR metadata ---
    ocr_text = models.TextField(blank=True)
    ocr_engine = models.CharField(max_length=40, blank=True)
    ocr_confidence = models.FloatField(null=True, blank=True)       # engine confidence 0-100
    extracted_snapshot = models.JSONField(default=dict, blank=True)  # what OCR/AI originally read
    ocr_accuracy = models.FloatField(null=True, blank=True)          # % fields left uncorrected by humans

    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                    related_name="uploaded_invoices")
    received_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return self.invoice_number or self.original_filename


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveIntegerField(default=1)
    item_code = models.CharField(max_length=40, blank=True)
    description = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    po_line = models.ForeignKey("purchasing.POLine", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="invoice_lines")

    class Meta:
        ordering = ["invoice_id", "line_no"]


class ValidationIssue(models.Model):
    class Category(models.TextChoices):
        MANDATORY = "MANDATORY", "Mandatory field"
        DUPLICATE = "DUPLICATE", "Duplicate"
        TAX = "TAX", "GST / tax"
        AMOUNT = "AMOUNT", "Amount"
        VENDOR = "VENDOR", "Vendor master"
        MATCH = "MATCH", "PO matching"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="issues")
    category = models.CharField(max_length=12, choices=Category.choices)
    severity = models.CharField(max_length=8, default="ERROR")   # ERROR blocks, WARNING doesn't
    message = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "id"]
