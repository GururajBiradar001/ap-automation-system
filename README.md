# AP Automation Software with OCR

Accounts Payable automation: invoice capture → OCR/AI extraction → validation → PO matching → approval workflow → payment → reporting.
**Stack (as mandated):** React (Vite) · Django + Django REST Framework · PostgreSQL.

## Quick start

### Option A – Docker (PostgreSQL included)
```bash
docker compose up --build            # API on :8000 (Postgres + Tesseract inside the image)
docker compose exec backend python manage.py seed_demo
cd frontend && npm install && npm run dev      # UI on :5173
```

### Option B – manual
Prerequisites: Python 3.11+, Node 18+, PostgreSQL 14+, **Tesseract** (`apt install tesseract-ocr poppler-utils` / `brew install tesseract poppler`).
```bash
createdb ap_automation                       # or: psql -c "create database ap_automation"
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                         # edit DATABASE_URL if needed
python manage.py migrate
python manage.py seed_demo                   # demo users, vendors, POs, GRN, approval matrix, sample invoices
python manage.py runserver                   # http://localhost:8000
# new terminal
cd frontend && npm install && npm run dev    # http://localhost:5173
```
Demo logins (password `Pass@1234`): `clerk`, `manager`, `finance`, `cfo`, `admin`.
Sample invoices to upload are generated into `sample_invoices/`.

Tests: `cd backend && python manage.py test invoices` (10 end-to-end tests).

## Module coverage (scope document)

| # | Module | Implementation |
|---|--------|----------------|
| 1 | Invoice capture | Drag & drop + bulk upload (UI + `POST /api/invoices/upload/`); PDF/JPG/PNG/TIFF; email ingestion via IMAP: `python manage.py ingest_emails` (or `--eml file`) |
| 2 | OCR & AI extraction | `pdfplumber` for digital PDFs, **Tesseract** for scans/images (table-line removal preprocessing), multi-page PDF + multi-frame TIFF, table/line-item extraction, rule-based field identification, optional LLM pass (`ANTHROPIC_API_KEY`) |
| 3 | Validation engine | Mandatory fields, duplicates (file hash + vendor/invoice no. + amount/date), GSTIN format + checksum, CGST/SGST vs IGST by place of supply, GST slab & tax recomputation, amount cross-checks, vendor master |
| 4 | PO matching | 2-way (PO↔Invoice) and 3-way (PO↔GRN↔Invoice); price tolerance, cumulative billed-vs-ordered/received quantity |
| 5 | Workflow & approvals | Configurable amount-based matrix, role-based, **parallel stages**, SLA escalation, reminders, responsive UI for mobile approval |
| 6 | Vendor management | Master data, bank accounts (IFSC/account validation, re-verify on change), GSTIN validation, onboarding workflow (draft → submit → manager approval) |
| 7 | Payments | Auto payment request on final approval, NEFT/RTGS selection, bank gateway adapter (mock), status tracking, payment advice PDF |
| 8 | Dashboard | Aging, pending approvals, turnaround, OCR accuracy, vendor analytics, payment tracking |
| 9 | Reports | AP aging, invoice status, exceptions, audit log, GST/tax register - all with CSV export |

## Architecture
```
React SPA ──REST/JSON (token auth)──► Django REST API ──► PostgreSQL
                                       │
        accounts   users+roles, audit log, notifications
        vendors    vendor master, bank accounts, GSTIN utils
        purchasing PO, PO lines, GRN
        invoices   models + services/{ocr, validation, matching, pipeline}
        workflow   approval matrix, tasks, engine (stages, escalation)
        payments   payment requests, bank gateway adapter, advice PDF
        reports    dashboard + report endpoints
```
Pipeline (`invoices/services/pipeline.py`): upload → OCR → save fields/lines → resolve vendor → validate → match → **exceptions queue** or **approval workflow** → payment.

Key design decisions
- Business logic lives in `services/` and `engine.py`, not in views, so it is unit-testable and reusable by the management commands.
- Everything important writes to `AuditLog` (append-only).
- OCR accuracy % = share of extracted header/line cells that humans did **not** correct before approval, a measurable KPI rather than the raw engine confidence (both are shown).
- Approval matrix is data (DB rows), not code. Same `stage` = parallel, next stage = sequential.
- Bank integration sits behind `payments/bank.py::BankGateway`; swap the mock for a real bank API without touching workflow code.

## Known limitations (honest list)
- OCR runs synchronously in the request; for production move it to Celery/RQ.
- Bank gateway is a mock; ERP integration is represented by PO/GRN APIs (`/api/purchase-orders/`, `/api/grns/`), not a live ERP connector.
- Rule-based extraction is tuned to common Indian GST invoice layouts; unusual layouts benefit from the optional LLM pass.
- GSTIN is validated structurally (format, state code, checksum), not against the live GST portal.
- No TDS/withholding, multi-currency FX, or e-invoice (IRN) handling.

## Deployment
Backend: any Docker host (Render, Railway, Fly) with managed PostgreSQL - set `DATABASE_URL`, `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`. Frontend: Vercel/Netlify with `VITE_API_URL=https://<backend>/api`.
Cron: `python manage.py process_escalations` every 15 min; `python manage.py ingest_emails` every 5 min.
