from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard),
    path("reports/ap-aging/", views.ap_aging),
    path("reports/invoice-status/", views.invoice_status),
    path("reports/exceptions/", views.exceptions),
    path("reports/audit-log/", views.audit_report),
    path("reports/gst/", views.gst_report),
]
