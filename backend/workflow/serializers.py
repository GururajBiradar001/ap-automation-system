from rest_framework import serializers
from .models import ApprovalRule, ApprovalStep, ApprovalTask


class ApprovalStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalStep
        fields = ["id", "stage", "role", "sla_hours", "escalation_role"]


class ApprovalRuleSerializer(serializers.ModelSerializer):
    steps = ApprovalStepSerializer(many=True)

    class Meta:
        model = ApprovalRule
        fields = ["id", "name", "min_amount", "max_amount", "is_active", "steps"]

    def create(self, validated):
        steps = validated.pop("steps")
        rule = ApprovalRule.objects.create(**validated)
        for s in steps:
            ApprovalStep.objects.create(rule=rule, **s)
        return rule

    def update(self, inst, validated):
        steps = validated.pop("steps", None)
        for k, v in validated.items():
            setattr(inst, k, v)
        inst.save()
        if steps is not None:
            inst.steps.all().delete()
            for s in steps:
                ApprovalStep.objects.create(rule=inst, **s)
        return inst


class ApprovalTaskSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    vendor_name = serializers.SerializerMethodField()
    amount = serializers.DecimalField(source="invoice.total_amount", max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = ApprovalTask
        fields = ["id", "invoice", "invoice_number", "vendor_name", "amount", "stage", "role", "status",
                  "due_at", "escalated", "comment", "decided_at"]

    def get_vendor_name(self, o):
        i = o.invoice
        return i.vendor.name if i.vendor_id else i.vendor_name_raw
