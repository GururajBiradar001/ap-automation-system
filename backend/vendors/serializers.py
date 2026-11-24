import re
from rest_framework import serializers
from .models import Vendor, VendorBank
from .gst import validate_gstin, pan_from_gstin, PAN_RE, IFSC_RE


class VendorBankSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorBank
        fields = ["id", "vendor", "account_name", "account_number", "ifsc", "bank_name",
                  "branch", "is_primary", "is_verified"]
        read_only_fields = ["is_verified"]

    def validate_ifsc(self, v):
        v = v.strip().upper()
        if not IFSC_RE.match(v):
            raise serializers.ValidationError("Invalid IFSC (format: ABCD0123456)")
        return v

    def validate_account_number(self, v):
        if not re.fullmatch(r"\d{9,18}", v.strip()):
            raise serializers.ValidationError("Account number must be 9-18 digits")
        return v.strip()


class VendorSerializer(serializers.ModelSerializer):
    banks = VendorBankSerializer(many=True, read_only=True)

    class Meta:
        model = Vendor
        fields = ["id", "code", "name", "gstin", "pan", "email", "phone", "address", "state_code",
                  "payment_terms_days", "status", "onboarding_comment", "banks", "created_at"]
        read_only_fields = ["code", "status", "onboarding_comment", "state_code", "pan"]

    def validate_gstin(self, v):
        v = v.strip().upper()
        if v:
            ok, msg = validate_gstin(v)
            if not ok:
                raise serializers.ValidationError(msg)
        return v

    def _derive(self, data):
        g = data.get("gstin")
        if g:
            data["state_code"] = g[:2]
            data["pan"] = pan_from_gstin(g)
        return data

    def create(self, validated):
        return super().create(self._derive(validated))

    def update(self, inst, validated):
        return super().update(inst, self._derive(validated))
