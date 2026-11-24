"""Orchestrates: OCR -> save -> validate -> match -> (exception | approval workflow)."""
import hashlib
from decimal import Decimal
from django.core.files.base import ContentFile
from django.utils import timezone

from accounts import audit
from ..models import Invoice, InvoiceLine
from . import ocr, validation, matching

SNAPSHOT_FIELDS = ["vendor_name_raw", "vendor_gstin", "invoice_number", "invoice_date", "due_date",
                   "po_number", "subtotal", "cgst", "sgst", "igst", "total_amount"]
ALLOWED_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff")


def _jsonable(v):
    return str(v) if v is not None else None


def snapshot_of(inv):
    d = {f: _jsonable(getattr(inv, f)) for f in SNAPSHOT_FIELDS}
    d["line_count"] = inv.lines.count()
    d["lines"] = [[str(l.item_code), str(l.description), str(l.quantity), str(l.unit_price), str(l.amount)]
                  for l in inv.lines.all()]
    return d


def create_invoice(uploaded_file, user=None, source="UPLOAD"):
    """Store the file and run the full pipeline. Returns the Invoice."""
    name = uploaded_file.name
    if not name.lower().endswith(ALLOWED_EXT):
        raise ValueError(f"Unsupported file type: {name} (allowed: PDF, JPG, PNG, TIFF)")
    content = uploaded_file.read()
    inv = Invoice(original_filename=name, file_hash=hashlib.sha256(content).hexdigest(),
                  source=source, uploaded_by=user)
    inv.file.save(name, ContentFile(content), save=True)
    audit.log(user, "INVOICE_RECEIVED", "Invoice", inv.pk, filename=name, source=source)
    process_invoice(inv, user)
    return inv


def run_ocr(inv):
    res = ocr.extract_invoice(inv.file.path)
    f = res["fields"]
    for k in SNAPSHOT_FIELDS:
        v = f.get(k)
        if v is None and k in ("cgst", "sgst", "igst"):
            v = Decimal(0)
        if v is not None:
            setattr(inv, k, v)
    inv.ocr_text, inv.page_count = res["text"], res["pages"]
    inv.ocr_engine, inv.ocr_confidence = res["engine"], res["confidence"]
    inv.save()
    inv.lines.all().delete()
    for i, l in enumerate(f.get("lines") or [], 1):
        InvoiceLine.objects.create(invoice=inv, line_no=i, item_code=l.get("item_code", ""),
                                   description=l.get("description", "")[:255], quantity=l["quantity"],
                                   unit_price=l["unit_price"], gst_rate=l.get("gst_rate") or 0, amount=l["amount"])
    inv.refresh_from_db()                   # canonical DB values, so 0 vs 0.00 never looks like a correction
    inv.extracted_snapshot = snapshot_of(inv)
    inv.save(update_fields=["extracted_snapshot"])


def compute_accuracy(inv):
    """OCR accuracy % = share of extracted fields (header + line cells) NOT corrected by a human."""
    snap, cur = inv.extracted_snapshot or {}, snapshot_of(inv)
    keys = SNAPSHOT_FIELDS
    total = len(keys) + sum(len(r) for r in snap.get("lines", []))
    same = sum(1 for k in keys if snap.get(k) == cur.get(k))
    for a, b in zip(snap.get("lines", []), cur["lines"]):
        same += sum(1 for x, y in zip(a, b) if x == y)
    return round(100.0 * same / total, 1) if total else None


def evaluate(inv, user=None):
    """Validate + match; route to EXCEPTION or into the approval workflow."""
    validation.run_validation(inv)
    inv.refresh_from_db()
    matching.run_matching(inv)
    inv.refresh_from_db()
    errors = inv.issues.filter(severity="ERROR").count()
    if errors:
        inv.status = Invoice.Status.EXCEPTION
        inv.save(update_fields=["status"])
        audit.log(user, "VALIDATION_FAILED", "Invoice", inv.pk, errors=errors)
    else:
        inv.ocr_accuracy = compute_accuracy(inv)
        inv.save(update_fields=["ocr_accuracy"])
        from workflow import engine
        engine.start_approval(inv, user)


def process_invoice(inv, user=None):
    run_ocr(inv)
    audit.log(user, "OCR_COMPLETED", "Invoice", inv.pk, engine=inv.ocr_engine,
              confidence=inv.ocr_confidence, pages=inv.page_count)
    validation.resolve_vendor(inv)
    inv.refresh_from_db()
    if inv.due_date is None and inv.invoice_date:
        terms = inv.vendor.payment_terms_days if inv.vendor_id else 30
        from datetime import timedelta
        inv.due_date = inv.invoice_date + timedelta(days=terms)
        inv.save(update_fields=["due_date"])
    evaluate(inv, user)
