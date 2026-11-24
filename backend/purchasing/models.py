from django.db import models
from django.db.models import Sum
from vendors.models import Vendor


class PurchaseOrder(models.Model):
    class MatchType(models.TextChoices):
        TWO_WAY = "2WAY", "2-way (PO vs Invoice)"
        THREE_WAY = "3WAY", "3-way (PO vs GRN vs Invoice)"

    po_number = models.CharField(max_length=40, unique=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="purchase_orders")
    po_date = models.DateField()
    match_type = models.CharField(max_length=4, choices=MatchType.choices, default=MatchType.TWO_WAY)
    status = models.CharField(max_length=10, default="OPEN")
    currency = models.CharField(max_length=3, default="INR")

    class Meta:
        ordering = ["-po_date"]

    def __str__(self):
        return self.po_number

    @property
    def total(self):
        return sum(l.quantity * l.unit_price for l in self.lines.all())


class POLine(models.Model):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveIntegerField()
    item_code = models.CharField(max_length=40, blank=True)
    description = models.CharField(max_length=255)
    uom = models.CharField(max_length=10, default="NOS")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18)

    class Meta:
        ordering = ["po_id", "line_no"]
        unique_together = ("po", "line_no")

    @property
    def received_qty(self):
        return self.grn_lines.aggregate(s=Sum("quantity_received"))["s"] or 0

    def invoiced_qty(self, exclude_invoice=None):
        """Quantity already billed on other live (non-rejected) invoices."""
        qs = self.invoice_lines.exclude(invoice__status="REJECTED")
        if exclude_invoice is not None:
            qs = qs.exclude(invoice=exclude_invoice)
        return qs.aggregate(s=Sum("quantity"))["s"] or 0


class GoodsReceipt(models.Model):
    grn_number = models.CharField(max_length=40, unique=True)
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="grns")
    received_date = models.DateField()

    class Meta:
        ordering = ["-received_date"]

    def __str__(self):
        return self.grn_number


class GRNLine(models.Model):
    grn = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name="lines")
    po_line = models.ForeignKey(POLine, on_delete=models.PROTECT, related_name="grn_lines")
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3)
