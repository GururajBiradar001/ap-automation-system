from rest_framework import viewsets
from .models import PurchaseOrder, GoodsReceipt
from .serializers import PurchaseOrderSerializer, GoodsReceiptSerializer


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.select_related("vendor").prefetch_related("lines")
    serializer_class = PurchaseOrderSerializer


class GoodsReceiptViewSet(viewsets.ModelViewSet):
    queryset = GoodsReceipt.objects.select_related("po").prefetch_related("lines")
    serializer_class = GoodsReceiptSerializer
