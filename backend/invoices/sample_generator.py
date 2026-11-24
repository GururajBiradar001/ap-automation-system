"""Generates realistic sample invoices (PDF, multi-page PDF, scanned PNG) for demo/testing."""
import os
from decimal import Decimal as D, ROUND_HALF_UP
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def q(x):
    return D(x).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def money(x):
    return f"{q(x):,.2f}"


def build(path, vendor, vgstin, buyer_gstin, inv_no, inv_date, due, po, lines, tax_mode="auto",
          force_total=None, wrong_tax=None):
    """lines: [(code, desc, qty, rate, gst_pct)]. tax_mode: 'intra' (CGST+SGST) | 'inter' (IGST)."""
    st = getSampleStyleSheet()
    sub = sum(q(D(qty) * D(rate)) for _, _, qty, rate, _ in lines)
    tax = sum(q(D(qty) * D(rate) * D(g) / 100) for _, _, qty, rate, g in lines)
    rate_pct = lines[0][4]
    els = [Paragraph("TAX INVOICE", st["Title"]),
           Paragraph(f"Supplier: {vendor}", st["Normal"]),
           Paragraph(f"GSTIN: {vgstin}", st["Normal"]), Spacer(1, 6),
           Paragraph("Bill To: Templegate Technologies &amp; Services Pvt. Ltd., Bengaluru", st["Normal"]),
           Paragraph(f"Buyer GSTIN: {buyer_gstin}", st["Normal"]), Spacer(1, 6),
           Paragraph(f"Invoice No: {inv_no}", st["Normal"]),
           Paragraph(f"Invoice Date: {inv_date}", st["Normal"]),
           Paragraph(f"Due Date: {due}", st["Normal"]),
           Paragraph(f"PO No: {po}", st["Normal"]), Spacer(1, 10)]
    rows = [["Sl", "Item Code", "Description", "Qty", "Rate", "GST %", "Amount"]]
    for i, (code, desc, qty, rate, g) in enumerate(lines, 1):
        rows.append([str(i), code, desc, str(qty), money(rate), str(g), money(D(qty) * D(rate))])
    t = Table(rows, repeatRows=1, colWidths=[24, 62, 175, 36, 62, 38, 70])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("FONTSIZE", (0, 0), (-1, -1), 8),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)]))
    els += [t, Spacer(1, 10), Paragraph(f"Subtotal: {money(sub)}", st["Normal"])]
    if tax_mode == "inter" or wrong_tax == "igst":
        els.append(Paragraph(f"IGST @ {rate_pct}%: {money(tax)}", st["Normal"]))
    else:
        els += [Paragraph(f"CGST @ {D(rate_pct) / 2}%: {money(tax / 2)}", st["Normal"]),
                Paragraph(f"SGST @ {D(rate_pct) / 2}%: {money(tax / 2)}", st["Normal"])]
    total = force_total if force_total is not None else sub + tax
    els.append(Paragraph(f"Total Amount: {money(total)}", st["Heading3"]))
    SimpleDocTemplate(path, pagesize=A4).build(els)
    return path


def rasterize(pdf_path, png_path, dpi=200):
    from pdf2image import convert_from_path
    convert_from_path(pdf_path, dpi=dpi)[0].save(png_path)


def generate_samples(out_dir, buyer_gstin, gstins):
    os.makedirs(out_dir, exist_ok=True)
    g1, g2, g3 = gstins
    p = lambda n: os.path.join(out_dir, n)
    build(p("INV-1001_clean_2way.pdf"), "Sharma Electricals Pvt Ltd", g1, buyer_gstin, "INV-1001", "15/11/2026",
          "15/12/2026", "PO-2026-001",
          [("ELC-101", "LED Panel Light 40W", 60, 850, 18), ("ELC-102", "Copper Wire 2.5mm (90m)", 30, 1450, 18)])
    build(p("INV-2001_clean_3way_parallel.pdf"), "Mehta Industrial Supplies", g2, buyer_gstin, "INV-2001",
          "16/11/2026", "16/12/2026", "PO-2026-002",
          [("MCH-201", "Hydraulic Pump HP-20", 6, 24500, 18), ("MCH-202", "Pressure Valve PV-5", 20, 3200, 18)],
          tax_mode="inter")
    build(p("INV-2002_overbilled_3way.pdf"), "Mehta Industrial Supplies", g2, buyer_gstin, "INV-2002",
          "18/11/2026", "18/12/2026", "PO-2026-002",
          [("MCH-201", "Hydraulic Pump HP-20", 4, 26000, 18)], tax_mode="inter")
    build(p("INV-4004_bad_tax.pdf"), "Sharma Electricals Pvt Ltd", g1, buyer_gstin, "INV-4004", "19/11/2026",
          "19/12/2026", "PO-2026-004", [("ELC-301", "Switch Gear Box", 5, 2000, 18)], wrong_tax="igst")
    items = [(f"STN-{i:03d}", f"Office Stationery Item {i}", 10, 40 + i, 12) for i in range(1, 31)]
    build(p("INV-3003_multipage.pdf"), "Kaveri Stationers", g3, buyer_gstin, "INV-3003", "20/11/2026",
          "20/12/2026", "PO-2026-003", items)
    scan_pdf = build(p("_tmp_scan.pdf"), "Kaveri Stationers", g3, buyer_gstin, "INV-5005", "21/11/2026",
                     "21/12/2026", "PO-2026-006", [("STN-900", "A4 Paper Ream 75GSM", 100, 320, 12)])
    rasterize(scan_pdf, p("INV-5005_scanned_image.png"))
    os.remove(scan_pdf)
    return sorted(os.listdir(out_dir))
