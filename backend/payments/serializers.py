from rest_framework import serializers
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    bank_label = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ["id", "payment_ref", "invoice", "invoice_number", "vendor", "vendor_name", "bank_label",
                  "amount", "mode", "status", "bank_reference", "failure_reason", "due_date",
                  "requested_at", "initiated_at", "paid_at"]

    def get_bank_label(self, o):
        return str(o.bank) if o.bank else None
