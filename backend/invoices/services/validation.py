"""Invoice Validation Engine: mandatory fields, duplicates, GST/tax, amounts, vendor master."""
from decimal import Decimal
from django.conf import settings

from vendors.gst import validate_gstin, pan_from_gstin
from vendors.models import Vendor
from ..models import Invoice, ValidationIssue

D = Decimal
TOL = D(str(settings.AMOUNT_TOLERANCE))


def _issue(inv, cat, msg, sev="ERROR"):
    ValidationIssue.objects.create(invoice=inv, category=cat, severity=sev, message=msg)


def validate_mandatory(inv):
    missing = []
    if not inv.vendor_name_raw and not inv.vendor_id:
        missing.append("vendor name")
    for field, label in (("invoice_number", "invoice number"), ("invoice_date", "invoice date"),
                         ("total_amount", "total amount"), ("vendor_gstin", "vendor GSTIN")):
        if not getattr(inv, field):
            missing.append(label)
    if not inv.lines.exists():
        missing.append("line items")
    for m in missing:
        _issue(inv, "MANDATORY", f"Missing mandatory field: {m}")
    if not inv.po_number:
        _issue(inv, "MANDATORY", "No PO reference - treated as non-PO invoice (manual approval)", "WARNING")


def validate_duplicate(inv):
    if inv.file_hash:
        dup = Invoice.objects.filter(file_hash=inv.file_hash).exclude(pk=inv.pk).exclude(status="REJECTED").first()
        if dup:
            _issue(inv, "DUPLICATE", f"Identical file already uploaded (invoice #{dup.pk})")
    if inv.vendor_id and inv.invoice_number:
        dup = (Invoice.objects.filter(vendor=inv.vendor, invoice_number__iexact=inv.invoice_number)
               .exclude(pk=inv.pk).exclude(status="REJECTED").first())
        if dup:
            _issue(inv, "DUPLICATE", f"Invoice number {inv.invoice_number} already exists for this vendor (#{dup.pk})")
    if inv.vendor_id and inv.total_amount and inv.invoice_date:
        dup = (Invoice.objects.filter(vendor=inv.vendor, total_amount=inv.total_amount,
                                      invoice_date=inv.invoice_date)
               .exclude(pk=inv.pk).exclude(status="REJECTED").exclude(invoice_number__iexact=inv.invoice_number).first())
        if dup:
            _issue(inv, "DUPLICATE", f"Same vendor, date and amount as invoice #{dup.pk} - possible duplicate", "WARNING")


def validate_tax(inv):
    g = inv.vendor_gstin
    if g:
        ok, msg = validate_gstin(g)
        if not ok:
            _issue(inv, "TAX", msg)
    cg, sg, ig = inv.cgst or D(0), inv.sgst or D(0), inv.igst or D(0)
    if ig and (cg or sg):
        _issue(inv, "TAX", "Invoice charges IGST together with CGST/SGST - not allowed")
    if abs(cg - sg) > TOL:
        _issue(inv, "TAX", "CGST and SGST amounts differ (they must be equal)")
    # Place of supply: same state => CGST+SGST, different state => IGST
    if g and len(g) >= 2 and settings.COMPANY_GSTIN:
        intra = g[:2] == settings.COMPANY_GSTIN[:2]
        if intra and ig:
            _issue(inv, "TAX", "Intra-state supply must carry CGST+SGST, but IGST was charged")
        if not intra and (cg or sg):
            _issue(inv, "TAX", "Inter-state supply must carry IGST, but CGST/SGST was charged")
    # Tax computed from line rates vs tax on invoice
    lines = list(inv.lines.all())
    for l in lines:
        if float(l.gst_rate) not in settings.ALLOWED_GST_RATES:
            _issue(inv, "TAX", f"Line {l.line_no}: GST rate {l.gst_rate}% is not a valid slab")
    if lines and any(l.gst_rate for l in lines):
        expected = sum((l.amount * l.gst_rate / 100 for l in lines), D(0))
        actual = cg + sg + ig
        if abs(expected - actual) > max(TOL, expected * D("0.005")):
            _issue(inv, "TAX", f"Tax mismatch: line GST rates give {expected:.2f} but invoice shows {actual:.2f}")
    # Vendor master GSTIN agreement
    if inv.vendor_id and inv.vendor.gstin and g and inv.vendor.gstin != g:
        _issue(inv, "TAX", f"GSTIN on invoice ({g}) differs from vendor master ({inv.vendor.gstin})")


def validate_amounts(inv):
    lines = list(inv.lines.all())
    if inv.total_amount is not None and inv.total_amount <= 0:
        _issue(inv, "AMOUNT", "Total amount must be greater than zero")
    for l in lines:
        if abs(l.quantity * l.unit_price - l.amount) > TOL:
            _issue(inv, "AMOUNT", f"Line {l.line_no}: qty x rate = {l.quantity * l.unit_price:.2f} but amount is {l.amount}")
    if lines and inv.subtotal is not None:
        s = sum((l.amount for l in lines), D(0))
        if abs(s - inv.subtotal) > TOL:
            _issue(inv, "AMOUNT", f"Sum of lines ({s:.2f}) does not equal subtotal ({inv.subtotal})")
    if inv.subtotal is not None and inv.total_amount is not None:
        calc = inv.subtotal + (inv.cgst or 0) + (inv.sgst or 0) + (inv.igst or 0)
        if abs(calc - inv.total_amount) > TOL:
            _issue(inv, "AMOUNT", f"Subtotal + tax = {calc:.2f} but invoice total is {inv.total_amount}")


def resolve_vendor(inv):
    """Link invoice to vendor master by GSTIN, then by exact (case-insensitive) name."""
    if inv.vendor_id:
        return
    v = None
    if inv.vendor_gstin:
        v = Vendor.objects.filter(gstin=inv.vendor_gstin).first()
    if not v and inv.vendor_name_raw:
        v = Vendor.objects.filter(name__iexact=inv.vendor_name_raw.strip()).first()
    if v:
        inv.vendor = v
        inv.save(update_fields=["vendor"])


def validate_vendor(inv):
    v = inv.vendor
    if not v:
        _issue(inv, "VENDOR", "Vendor not found in vendor master")
        return
    if v.status != Vendor.Status.ACTIVE:
        _issue(inv, "VENDOR", f"Vendor {v.code} is not active (status: {v.get_status_display()})")
    if not v.banks.filter(is_verified=True).exists():
        _issue(inv, "VENDOR", "Vendor has no verified bank account - payment cannot be released", "WARNING")


def run_validation(inv):
    inv.issues.exclude(category="MATCH").delete()
    resolve_vendor(inv)
    inv.refresh_from_db()
    validate_mandatory(inv)
    validate_duplicate(inv)
    validate_tax(inv)
    validate_amounts(inv)
    validate_vendor(inv)
