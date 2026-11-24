# Challenges and Solutions

1. **Scanned invoices lost their table.** Tesseract's default mode scattered table cells onto separate lines and `--psm 6` dropped the table entirely because of the grid borders.
   *Solution:* a preprocessing step removes long horizontal/vertical ruling lines (numpy run-length detection) before OCR in `--psm 6`; each table row then comes out on one line and is parsed with a row regex. Digital PDFs use `pdfplumber` table extraction first.
2. **Meaningful "OCR accuracy".** Engine confidence says little about whether the extracted values are right.
   *Solution:* snapshot what OCR extracted, and when the invoice enters approval compare it with the (possibly human-corrected) values. A first bug showed 95% on perfect invoices because `0` and `0.00` compared as different strings; the snapshot is now taken from canonical DB values.
3. **Parallel + sequential approvals.** Needed both "Manager and Finance at the same time" and "then CFO".
   *Solution:* each approval step has a `stage`; steps sharing a stage run in parallel and the next stage is created only when every task of the stage is approved. Any rejection cancels the rest.
4. **Escalation without a scheduler.** *Solution:* escalation/reminder logic is a plain function (`run_escalations`) exposed as a management command (cron) and an API button, and covered by a test that back-dates a task.
5. **GST correctness.** Needed more than a regex. *Solution:* GSTIN checksum (mod-36), state-code check, place-of-supply rule (CGST+SGST vs IGST using the company GSTIN), slab check and tax recomputation from line rates.
6. **3-way matching across several invoices.** Partial deliveries and multiple invoices per PO line. *Solution:* the matcher compares cumulative billed quantity (other live invoices + this one) against PO quantity (2-way) or received GRN quantity (3-way).
7. **Environment limits.** PostgreSQL could not be installed in the build sandbox, so the code was developed against PostgreSQL-compatible settings and verified on SQLite; the PostgreSQL DDL is generated from the same models (`export_schema`). Re-run the test suite against Postgres on your machine (`DATABASE_URL` pointing to it).
8. **One bad file in a bulk upload.** Each file is processed independently and errors are returned per file, so a batch never fails as a whole.
