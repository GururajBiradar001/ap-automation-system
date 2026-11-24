from django.contrib import admin
from .models import ApprovalRule, ApprovalStep, ApprovalTask
for m in (ApprovalRule, ApprovalStep, ApprovalTask):
    admin.site.register(m)
