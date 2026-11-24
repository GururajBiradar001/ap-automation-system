from django.contrib import admin
from .models import Invoice, InvoiceLine, ValidationIssue
for m in (Invoice, InvoiceLine, ValidationIssue):
    admin.site.register(m)
