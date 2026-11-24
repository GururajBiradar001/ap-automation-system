from django.contrib import admin
from .models import PurchaseOrder, POLine, GoodsReceipt, GRNLine
for m in (PurchaseOrder, POLine, GoodsReceipt, GRNLine):
    admin.site.register(m)
