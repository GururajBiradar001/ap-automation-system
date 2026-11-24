from django.utils import timezone

from accounts import audit
from .bank import choose_mode, get_gateway
from .models import Payment


def create_payment_request(invoice, user=None):
    """Called automatically when an invoice is fully approved."""
    bank = (invoice.vendor.banks.filter(is_verified=True).order_by("-is_primary").first()
            if invoice.vendor_id else None)
    p = Payment.objects.create(invoice=invoice, vendor=invoice.vendor, bank=bank, amount=invoice.total_amount,
                               mode=choose_mode(invoice.total_amount), due_date=invoice.due_date)
    invoice.status = "PAYMENT_REQUESTED"
    invoice.save(update_fields=["status"])
    audit.log(user, "PAYMENT_REQUESTED", "Invoice", invoice.pk, payment=p.payment_ref, amount=str(p.amount))
    audit.notify(f"Payment request {p.payment_ref}", f"{invoice.vendor.name}: {p.amount}", "/payments",
                 role="FINANCE_HEAD")
    return p


def release_payment(payment, user):
    """Send to the bank; on success mark paid and close the invoice."""
    if payment.status not in ("REQUESTED", "FAILED"):
        raise ValueError(f"Payment is already {payment.status}")
    payment.status, payment.initiated_at, payment.released_by = "INITIATED", timezone.now(), user
    payment.save()
    res = get_gateway().transfer(payment)
    if res["ok"]:
        payment.status, payment.bank_reference, payment.paid_at = "PAID", res["utr"], timezone.now()
        payment.failure_reason = ""
        payment.save()
        inv = payment.invoice
        inv.status, inv.paid_at = "PAID", payment.paid_at
        inv.save(update_fields=["status", "paid_at"])
        audit.log(user, "PAYMENT_PAID", "Invoice", inv.pk, payment=payment.payment_ref, utr=res["utr"])
    else:
        payment.status, payment.failure_reason = "FAILED", res["reason"]
        payment.save()
        audit.log(user, "PAYMENT_FAILED", "Invoice", payment.invoice_id, reason=res["reason"])
    return payment
