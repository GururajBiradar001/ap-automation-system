"""Payment advice (remittance advice) PDF generation."""
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def build_advice_pdf(p):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=f"Payment Advice {p.payment_ref}")
    st = getSampleStyleSheet()
    inv = p.invoice
    rows = [["Payment reference", p.payment_ref], ["Date", f"{(p.paid_at or p.requested_at):%d %b %Y}"],
            ["Mode", p.mode], ["Bank reference (UTR)", p.bank_reference or "-"],
            ["Beneficiary", p.vendor.name], ["Bank account", str(p.bank) if p.bank else "-"],
            ["Invoice number", inv.invoice_number], ["Invoice date", f"{inv.invoice_date}"],
            ["Invoice amount", f"INR {inv.total_amount}"], ["Amount paid", f"INR {p.amount}"],
            ["Status", p.get_status_display()]]
    t = Table(rows, colWidths=[150, 330])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                           ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke)]))
    doc.build([Paragraph("Payment Advice", st["Title"]),
               Paragraph(f"To: {p.vendor.name}", st["Normal"]), Spacer(1, 12), t, Spacer(1, 18),
               Paragraph("This is a system generated advice and does not require a signature.", st["Italic"])])
    return buf.getvalue()
