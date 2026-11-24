from django.conf import settings
from django.db import models


class Vendor(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
        ACTIVE = "ACTIVE", "Active"
        REJECTED = "REJECTED", "Rejected"
        BLOCKED = "BLOCKED", "Blocked"

    code = models.CharField(max_length=20, unique=True, blank=True)
    name = models.CharField(max_length=200)
    gstin = models.CharField(max_length=15, blank=True, db_index=True)
    pan = models.CharField(max_length=10, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    state_code = models.CharField(max_length=2, blank=True)
    payment_terms_days = models.PositiveIntegerField(default=30)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    onboarding_comment = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                   related_name="vendors_created")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="vendors_approved")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"V{self.pk:04d}"
            super().save(update_fields=["code"])

    def __str__(self):
        return f"{self.code} {self.name}"


class VendorBank(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="banks")
    account_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=20)
    ifsc = models.CharField(max_length=11)
    bank_name = models.CharField(max_length=100, blank=True)
    branch = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.bank_name} ****{self.account_number[-4:]}"
