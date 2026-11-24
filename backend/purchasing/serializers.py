from rest_framework import serializers
from .models import PurchaseOrder, POLine, GoodsReceipt, GRNLine


class POLineSerializer(serializers.ModelSerializer):
    received_qty = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)

    class Meta:
        model = POLine
        fields = ["id", "line_no", "item_code", "description", "uom", "quantity", "unit_price",
                  "gst_rate", "received_qty"]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    lines = POLineSerializer(many=True)
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = ["id", "po_number", "vendor", "vendor_name", "po_date", "match_type", "status",
                  "currency", "total", "lines"]

    def create(self, validated):
        lines = validated.pop("lines")
        po = PurchaseOrder.objects.create(**validated)
        for l in lines:
            POLine.objects.create(po=po, **l)
        return po


class GRNLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = GRNLine
        fields = ["id", "po_line", "quantity_received"]


class GoodsReceiptSerializer(serializers.ModelSerializer):
    lines = GRNLineSerializer(many=True)
    po_number = serializers.CharField(source="po.po_number", read_only=True)

    class Meta:
        model = GoodsReceipt
        fields = ["id", "grn_number", "po", "po_number", "received_date", "lines"]

    def create(self, validated):
        lines = validated.pop("lines")
        grn = GoodsReceipt.objects.create(**validated)
        for l in lines:
            GRNLine.objects.create(grn=grn, **l)
        return grn
