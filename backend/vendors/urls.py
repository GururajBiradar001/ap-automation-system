from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("vendors", views.VendorViewSet, basename="vendor")
router.register("vendor-banks", views.VendorBankViewSet, basename="vendorbank")
urlpatterns = [path("", include(router.urls))]
