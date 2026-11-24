from django.conf import settings
from django.db import models


class Payment(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        INITIATED = "INITIATED", "Initiated with bank"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"

    payment_ref = models.CharField(max_length=20, unique=True, blank=True)
    invoice = models.ForeignKey("invoices.Invoice", on_delete=models.PROTECT, related_name="payments")
    vendor = models.ForeignKey("vendors.Vendor", on_delete=models.PROTECT, related_name="payments")
    bank = models.ForeignKey("vendors.VendorBank", null=True, blank=True, on_delete=models.SET_NULL)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    mode = models.CharField(max_length=6, default="NEFT")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    bank_reference = models.CharField(max_length=40, blank=True)      # UTR from bank
    failure_reason = models.CharField(max_length=200, blank=True)
    due_date = models.DateField(null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    initiated_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-requested_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.payment_ref:
            self.payment_ref = f"PAY-{self.pk:06d}"
            super().save(update_fields=["payment_ref"])
