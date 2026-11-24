"""
OCR & AI extraction.

Pipeline:  file -> text (native PDF text, else Tesseract OCR per page/frame)
           -> structured fields (rule-based parser, tables first)
           -> optional LLM pass (Anthropic API) that fills/overrides fields when ANTHROPIC_API_KEY is set.
Multi-page PDFs and multi-frame TIFFs are handled page by page and merged.
"""
import json
import re
import urllib.request
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings

GSTIN_FIND = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
NUM = r"([\d,]+(?:\.\d+)?)"
DATE_PAT = r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})"


# ---------------------------------------------------------------- text extraction
def _remove_table_lines(img):
    """Erase long horizontal/vertical ruling lines so Tesseract can read table rows as text lines."""
    import numpy as np
    from PIL import Image
    g = np.array(img.convert("L"))
    dark = g < 140
    h, w = dark.shape
    out = g.copy()

    def longest_run(v):
        idx = np.flatnonzero(np.diff(np.concatenate(([0], v.view(np.int8), [0]))))
        return int((idx[1::2] - idx[::2]).max()) if len(idx) else 0
    for y in np.flatnonzero(dark.sum(axis=1) > w * 0.1):
        if longest_run(dark[y]) > w * 0.2:
            out[y, :] = 255
    for x in np.flatnonzero(dark.sum(axis=0) > 60):
        if longest_run(dark[:, x]) > 60:
            out[:, x] = 255
    return Image.fromarray(out)


def _ocr_image(img):
    import pytesseract
    try:
        img = _remove_table_lines(img)
    except Exception:                      # preprocessing is best-effort
        pass
    cfg = "--psm 6"                        # treat the page as uniform text rows (keeps table rows on one line)
    data = pytesseract.image_to_data(img, config=cfg, output_type=pytesseract.Output.DICT)
    confs = [float(c) for w, c in zip(data["text"], data["conf"]) if w.strip() and float(c) >= 0]
    text = pytesseract.image_to_string(img, config=cfg)
    return text, (sum(confs) / len(confs) if confs else 0.0)


def extract_text(path):
    """Returns dict(text, pages, confidence, engine, tables)."""
    lower = str(path).lower()
    texts, confs, tables, engine = [], [], [], "pdf-text"
    if lower.endswith(".pdf"):
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            pages = len(pdf.pages)
            for page in pdf.pages:
                t = (page.extract_text() or "").strip()
                if len(t) >= 30:                         # digital PDF
                    texts.append(t)
                    confs.append(100.0)
                    tables.extend(page.extract_tables() or [])
                else:                                    # scanned PDF -> rasterise + OCR
                    engine = "tesseract"
                    from pdf2image import convert_from_path
                    img = convert_from_path(path, dpi=250, first_page=page.page_number,
                                            last_page=page.page_number)[0]
                    tx, cf = _ocr_image(img)
                    texts.append(tx)
                    confs.append(cf)
    else:                                                # JPG / PNG / TIFF (multi-frame ok)
        from PIL import Image, ImageSequence
        engine = "tesseract"
        img = Image.open(path)
        frames = [f.convert("RGB") for f in ImageSequence.Iterator(img)]
        pages = len(frames)
        for fr in frames:
            tx, cf = _ocr_image(fr)
            texts.append(tx)
            confs.append(cf)
    return {"text": "\n".join(texts), "pages": pages, "engine": engine, "tables": tables,
            "confidence": round(sum(confs) / len(confs), 1) if confs else 0.0}


# ---------------------------------------------------------------- parsing helpers
def to_dec(s):
    try:
        return Decimal(str(s).replace(",", "").replace("₹", "").replace("Rs.", "").strip())
    except (InvalidOperation, AttributeError):
        return None


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y",
                "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _find(pattern, text, flags=re.I):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def _amount(label_regex, text):
    m = re.search(label_regex + r"[^\d\n]{0,25}" + NUM, text, re.I)
    return to_dec(m.group(1)) if m else None


def _parse_line_tables(tables):
    """Map pdfplumber tables with a recognisable header to line items."""
    lines = []
    for tb in tables:
        if not tb or len(tb) < 2:
            continue
        header = [(c or "").strip().lower() for c in tb[0]]

        def col(*names):
            for i, h in enumerate(header):
                if any(n in h for n in names):
                    return i
            return None
        c_desc, c_qty = col("description", "item", "material"), col("qty", "quantity")
        c_rate, c_amt = col("rate", "price"), col("amount", "total", "value")
        if c_desc is None or c_qty is None or c_amt is None:
            continue
        c_code, c_gst = col("code", "hsn", "sku"), col("gst", "tax")
        for row in tb[1:]:
            if not row or not (row[c_desc] or "").strip():
                continue
            qty, amt = to_dec(row[c_qty]), to_dec(row[c_amt])
            if qty is None or amt is None:
                continue
            rate = to_dec(row[c_rate]) if c_rate is not None else None
            gst = to_dec((row[c_gst] or "").replace("%", "")) if c_gst is not None else None
            lines.append({
                "item_code": (row[c_code] or "").strip() if c_code is not None else "",
                "description": " ".join((row[c_desc] or "").split()),
                "quantity": qty, "unit_price": rate if rate is not None else (amt / qty if qty else 0),
                "gst_rate": gst or Decimal(0), "amount": amt})
    return lines


LINE_RE = re.compile(
    r"^\s*(?:\d{1,3}\s+)?(?:(?P<code>[A-Z0-9][A-Z0-9\-]{2,})\s+)?(?P<desc>.+?)\s+(?P<qty>[\d,]+(?:\.\d+)?)\s+"
    r"(?:[A-Za-z]{2,5}\s+)?(?P<rate>[\d,]+\.\d{2})\s+(?:(?P<gst>\d{1,2}(?:\.\d+)?)\s*%?\s+)?(?P<amt>[\d,]+\.\d{2})\s*$",
    re.M)


def _parse_line_text(text):
    lines = []
    for m in LINE_RE.finditer(text):
        lines.append({"item_code": m.group("code") or "", "description": m.group("desc").strip(),
                      "quantity": to_dec(m.group("qty")), "unit_price": to_dec(m.group("rate")),
                      "gst_rate": to_dec(m.group("gst")) if m.group("gst") else Decimal(0),
                      "amount": to_dec(m.group("amt"))})
    return lines


def parse_fields(text, tables=()):
    """Rule-based field identification."""
    company = settings.COMPANY_GSTIN
    gstins = [g for g in GSTIN_FIND.findall(text) if g != company]
    vendor = _find(r"(?:Supplier|Vendor|Bill\s*From|Sold\s*By)\s*[:\-]\s*(.+)", text)
    if not vendor:
        first = next((l.strip() for l in text.splitlines() if l.strip()), "")
        vendor = first if first and "invoice" not in first.lower() else ""
    f = {
        "vendor_name_raw": vendor or "",
        "vendor_gstin": gstins[0] if gstins else "",
        "invoice_number": _find(r"Invoice\s*(?:No\.?|Number|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]+)", text) or "",
        "invoice_date": parse_date(_find(r"Invoice\s*Date\s*[:\-]?\s*" + DATE_PAT, text)),
        "due_date": parse_date(_find(r"Due\s*Date\s*[:\-]?\s*" + DATE_PAT, text)),
        "po_number": _find(r"(?:PO|P\.O\.|Purchase\s*Order)\s*(?:No\.?|Number|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]+)", text) or "",
        "subtotal": _amount(r"(?:Sub\s*-?\s*total|Taxable\s*(?:Value|Amount))", text),
        "cgst": _amount(r"CGST(?:\s*[(@]?\s*[\d.]+\s*%\)?)?", text),
        "sgst": _amount(r"SGST(?:\s*[(@]?\s*[\d.]+\s*%\)?)?", text),
        "igst": _amount(r"IGST(?:\s*[(@]?\s*[\d.]+\s*%\)?)?", text),
        "total_amount": _amount(r"(?:Grand\s*Total|Total\s*Amount|Invoice\s*Total|Amount\s*Payable)", text),
    }
    f["lines"] = _parse_line_tables(tables) or _parse_line_text(text)
    return f


# ---------------------------------------------------------------- AI (LLM) pass
LLM_PROMPT = (
    "Extract invoice data from the OCR text below. Reply with ONLY JSON with keys: vendor_name_raw, "
    "vendor_gstin, invoice_number, invoice_date (YYYY-MM-DD), due_date (YYYY-MM-DD), po_number, subtotal, "
    "cgst, sgst, igst, total_amount, lines (list of {item_code, description, quantity, unit_price, "
    "gst_rate, amount}). Use null for anything not present. Numbers must be plain numbers.\n\n")


def ai_extract(text):
    """Optional AI-based field identification via Anthropic API; returns {} if not configured/failed."""
    if not settings.ANTHROPIC_API_KEY:
        return {}
    try:
        body = json.dumps({"model": settings.LLM_MODEL, "max_tokens": 2000,
                           "messages": [{"role": "user", "content": LLM_PROMPT + text[:12000]}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
            "content-type": "application/json", "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.loads(r.read())["content"][0]["text"]
        data = json.loads(out[out.index("{"): out.rindex("}") + 1])
    except Exception:
        return {}
    for k in ("subtotal", "cgst", "sgst", "igst", "total_amount"):
        data[k] = to_dec(data[k]) if data.get(k) is not None else None
    for k in ("invoice_date", "due_date"):
        data[k] = parse_date(data.get(k))
    for l in data.get("lines") or []:
        for k in ("quantity", "unit_price", "gst_rate", "amount"):
            l[k] = to_dec(l.get(k)) or Decimal(0)
    return data


def extract_invoice(path):
    raw = extract_text(path)
    fields = parse_fields(raw["text"], raw["tables"])
    ai = ai_extract(raw["text"])
    engine = raw["engine"]
    if ai:                                  # AI fills gaps and corrects weak OCR parses
        for k, v in ai.items():
            if v not in (None, "", []) and (not fields.get(k) or k == "lines"):
                fields[k] = v
        engine += "+llm"
    return {"fields": fields, "text": raw["text"], "pages": raw["pages"],
            "confidence": raw["confidence"], "engine": engine}
