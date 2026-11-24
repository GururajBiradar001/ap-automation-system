"""PO Matching: 2-way (PO vs Invoice) and 3-way (PO vs GRN vs Invoice)."""
from decimal import Decimal
from difflib import SequenceMatcher
from django.conf import settings

from purchasing.models import PurchaseOrder
from ..models import ValidationIssue


def _issue(inv, msg, sev="ERROR"):
    ValidationIssue.objects.create(invoice=inv, category="MATCH", severity=sev, message=msg)


def _find_po_line(po, line):
    lines = list(po.lines.all())
    if line.item_code:
        for pl in lines:
            if pl.item_code and pl.item_code.upper() == line.item_code.upper():
                return pl
    best, score = None, 0.0
    for pl in lines:
        r = SequenceMatcher(None, pl.description.lower(), (line.description or "").lower()).ratio()
        if r > score:
            best, score = pl, r
    return best if score >= 0.6 else None


def run_matching(inv):
    inv.issues.filter(category="MATCH").delete()
    inv.lines.update(po_line=None)
    inv.purchase_order = None
    inv.match_type_used = ""
    if not inv.po_number:
        inv.save(update_fields=["purchase_order", "match_type_used"])
        return                                   # non-PO invoice: warning raised by mandatory validation

    po = PurchaseOrder.objects.filter(po_number__iexact=inv.po_number.strip()).first()
    if not po:
        _issue(inv, f"PO {inv.po_number} not found")
        inv.save(update_fields=["purchase_order", "match_type_used"])
        return
    inv.purchase_order = po
    inv.match_type_used = po.match_type
    inv.save(update_fields=["purchase_order", "match_type_used"])

    if inv.vendor_id and po.vendor_id != inv.vendor_id:
        _issue(inv, f"PO {po.po_number} belongs to a different vendor ({po.vendor.name})")
    three_way = po.match_type == PurchaseOrder.MatchType.THREE_WAY
    if three_way and not po.grns.exists():
        _issue(inv, f"3-way match: no goods receipt (GRN) recorded for PO {po.po_number}")

    tol = Decimal(str(settings.PRICE_TOLERANCE_PCT)) / 100
    for l in inv.lines.all():
        pl = _find_po_line(po, l)
        if not pl:
            _issue(inv, f"Line {l.line_no} ({l.description[:30]}) is not on PO {po.po_number}")
            continue
        l.po_line = pl
        l.save(update_fields=["po_line"])
        if pl.unit_price and abs(l.unit_price - pl.unit_price) / pl.unit_price > tol:
            _issue(inv, f"Line {l.line_no}: price {l.unit_price} differs from PO price {pl.unit_price} "
                        f"(tolerance {settings.PRICE_TOLERANCE_PCT}%)")
        already = pl.invoiced_qty(exclude_invoice=inv)
        if already + l.quantity > pl.quantity:                       # 2-way: PO quantity cap
            _issue(inv, f"Line {l.line_no}: billed qty {already + l.quantity} exceeds PO qty {pl.quantity}")
        elif three_way and already + l.quantity > pl.received_qty:   # 3-way: GRN quantity cap
            _issue(inv, f"Line {l.line_no}: billed qty {already + l.quantity} exceeds received qty "
                        f"{pl.received_qty} (GRN)")
