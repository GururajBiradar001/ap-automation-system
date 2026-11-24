from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("purchase-orders", views.PurchaseOrderViewSet, basename="po")
router.register("grns", views.GoodsReceiptViewSet, basename="grn")
urlpatterns = [path("", include(router.urls))]
