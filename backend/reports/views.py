import csv
from collections import defaultdict
from decimal import Decimal

from django.db.models import Avg, Count, Sum, F, ExpressionWrapper, DurationField
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import AuditLog
from invoices.models import Invoice, ValidationIssue
from payments.models import Payment
from workflow.models import ApprovalTask
from accounts.permissions import roles_required

OPEN_STATUSES = ["EXCEPTION", "PENDING_APPROVAL", "APPROVED", "PAYMENT_REQUESTED"]
BUCKETS = [("Not due", None, 0), ("1-30", 1, 30), ("31-60", 31, 60), ("61-90", 61, 90), ("90+", 91, 10**6)]


def _f(x):
    return float(x or 0)


def _bucket(days_overdue):
    for label, lo, hi in BUCKETS:
        if lo is None:
            if days_overdue <= 0:
                return label
        elif lo <= days_overdue <= hi:
            return label


def _respond(request, columns, rows, title=""):
    """Every report returns {columns, rows}; ?export=csv returns a CSV download."""
    if request.query_params.get("export") == "csv":
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{title or "report"}.csv"'
        w = csv.writer(resp)
        w.writerow(columns)
        w.writerows(rows)
        return resp
    return Response({"title": title, "columns": columns, "rows": rows})


def _aging_buckets(qs):
    today = timezone.localdate()
    out = {label: {"count": 0, "amount": 0.0} for label, *_ in BUCKETS}
    for i in qs:
        due = i.due_date or i.invoice_date or today
        b = _bucket((today - due).days)
        out[b]["count"] += 1
        out[b]["amount"] += _f(i.total_amount)
    return out


@api_view(["GET"])
def dashboard(request):
    invs = Invoice.objects.all()
    open_invs = invs.filter(status__in=OPEN_STATUSES)
    done = invs.filter(approved_at__isnull=False)
    tat_approve = [(i.approved_at - i.received_at).total_seconds() / 3600 for i in done]
    paid = invs.filter(paid_at__isnull=False)
    tat_paid = [(i.paid_at - i.received_at).total_seconds() / 3600 for i in paid]
    acc = invs.exclude(ocr_accuracy__isnull=True).aggregate(a=Avg("ocr_accuracy"))["a"]
    conf = invs.exclude(ocr_confidence__isnull=True).aggregate(a=Avg("ocr_confidence"))["a"]
    vendors = (invs.exclude(status="REJECTED").exclude(vendor__isnull=True)
               .values("vendor__name").annotate(count=Count("id"), total=Sum("total_amount"))
               .order_by("-total")[:8])
    pay = {s: {"count": 0, "amount": 0.0} for s, _ in Payment.Status.choices}
    for r in Payment.objects.values("status").annotate(c=Count("id"), a=Sum("amount")):
        pay[r["status"]] = {"count": r["c"], "amount": _f(r["a"])}
    u = request.user
    my_pending = ApprovalTask.objects.filter(status="PENDING", **({} if u.role == "ADMIN" or u.is_superuser else {"role": u.role})).count()
    return Response({
        "totals": {"invoices": invs.count(), "open_amount": _f(open_invs.aggregate(s=Sum("total_amount"))["s"]),
                   "exceptions": invs.filter(status="EXCEPTION").count()},
        "status_counts": {r["status"]: r["c"] for r in invs.values("status").annotate(c=Count("id"))},
        "aging": _aging_buckets(open_invs.exclude(status="EXCEPTION")),
        "pending_approvals": {"all": ApprovalTask.objects.filter(status="PENDING").count(), "mine": my_pending},
        "turnaround_hours": {"to_approval": round(sum(tat_approve) / len(tat_approve), 2) if tat_approve else None,
                             "to_payment": round(sum(tat_paid) / len(tat_paid), 2) if tat_paid else None},
        "ocr": {"accuracy_pct": round(acc, 1) if acc is not None else None,
                "engine_confidence_pct": round(conf, 1) if conf is not None else None},
        "vendors": [{"name": v["vendor__name"], "count": v["count"], "total": _f(v["total"])} for v in vendors],
        "payments": pay,
    })


@api_view(["GET"])
def ap_aging(request):
    today = timezone.localdate()
    rows = defaultdict(lambda: {l: Decimal(0) for l, *_ in BUCKETS})
    for i in Invoice.objects.filter(status__in=["APPROVED", "PAYMENT_REQUESTED"]).select_related("vendor"):
        due = i.due_date or i.invoice_date or today
        rows[i.vendor.name if i.vendor_id else i.vendor_name_raw][_bucket((today - due).days)] += i.total_amount or 0
    labels = [l for l, *_ in BUCKETS]
    data = [[v] + [_f(b[l]) for l in labels] + [_f(sum(b.values()))] for v, b in sorted(rows.items())]
    return _respond(request, ["Vendor"] + labels + ["Total"], data, "ap-aging")


@api_view(["GET"])
def invoice_status(request):
    qs = Invoice.objects.select_related("vendor")
    p = request.query_params
    if p.get("status"):
        qs = qs.filter(status=p["status"])
    if p.get("from"):
        qs = qs.filter(invoice_date__gte=p["from"])
    if p.get("to"):
        qs = qs.filter(invoice_date__lte=p["to"])
    rows = [[i.id, i.invoice_number, i.vendor.name if i.vendor_id else i.vendor_name_raw, str(i.invoice_date or ""),
             _f(i.total_amount), i.get_status_display(), i.source, f"{i.received_at:%Y-%m-%d %H:%M}"] for i in qs]
    return _respond(request, ["ID", "Invoice #", "Vendor", "Invoice date", "Amount", "Status", "Source", "Received"],
                    rows, "invoice-status")


@api_view(["GET"])
def exceptions(request):
    qs = ValidationIssue.objects.filter(severity="ERROR").select_related("invoice", "invoice__vendor") \
        .exclude(invoice__status="REJECTED")
    rows = [[x.invoice_id, x.invoice.invoice_number,
             x.invoice.vendor.name if x.invoice.vendor_id else x.invoice.vendor_name_raw,
             x.get_category_display(), x.message, x.invoice.get_status_display()] for x in qs]
    return _respond(request, ["Invoice ID", "Invoice #", "Vendor", "Category", "Exception", "Invoice status"],
                    rows, "exceptions")


@api_view(["GET"])
@permission_classes([roles_required("MANAGER", "FINANCE_HEAD", "CFO")])
def audit_report(request):
    qs = AuditLog.objects.select_related("user")
    p = request.query_params
    if p.get("entity_type"):
        qs = qs.filter(entity_type=p["entity_type"])
    if p.get("entity_id"):
        qs = qs.filter(entity_id=p["entity_id"])
    rows = [[f"{a.created_at:%Y-%m-%d %H:%M:%S}", a.user.username if a.user else "system", a.action,
             a.entity_type, a.entity_id, str(a.details)] for a in qs[:2000]]
    return _respond(request, ["Time", "User", "Action", "Entity", "Entity ID", "Details"], rows, "audit-log")


@api_view(["GET"])
def gst_report(request):
    """Input-tax (ITC) register for approved/paid invoices, optional ?month=YYYY-MM."""
    qs = Invoice.objects.filter(status__in=["APPROVED", "PAYMENT_REQUESTED", "PAID"]).select_related("vendor")
    m = request.query_params.get("month")
    if m:
        y, mo = m.split("-")
        qs = qs.filter(invoice_date__year=y, invoice_date__month=mo)
    rows, tot = [], [Decimal(0)] * 5
    for i in qs:
        vals = [i.subtotal or 0, i.cgst, i.sgst, i.igst, i.total_amount or 0]
        tot = [a + b for a, b in zip(tot, vals)]
        rows.append([i.invoice_number, str(i.invoice_date), i.vendor.name if i.vendor_id else i.vendor_name_raw,
                     i.vendor_gstin] + [_f(v) for v in vals])
    rows.append(["TOTAL", "", "", ""] + [_f(v) for v in tot])
    return _respond(request, ["Invoice #", "Date", "Vendor", "GSTIN", "Taxable value", "CGST", "SGST", "IGST",
                              "Invoice total"], rows, "gst-report")
