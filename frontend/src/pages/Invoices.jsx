import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, inr } from "../api";

export const StatusPill = ({ s }) => <span className={"pill " + s}>{(s || "").replaceAll("_", " ")}</span>;
const STATUSES = ["", "EXCEPTION", "PENDING_APPROVAL", "APPROVED", "PAYMENT_REQUESTED", "PAID", "REJECTED"];

export default function Invoices() {
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState(null);
  const input = useRef();

  const load = () => api.get(`/invoices/?status=${status}&q=${encodeURIComponent(q)}`).then((d) => setRows(d.results || []));
  useEffect(() => { load(); }, [status]);

  const upload = async (files) => {
    if (!files.length) return;
    const fd = new FormData();
    [...files].forEach((f) => fd.append("files", f));
    setBusy(true); setResults(null);
    try { setResults((await api.post("/invoices/upload/", fd)).results); await load(); }
    catch (e) { setResults([{ filename: "upload", error: e.message }]); }
    finally { setBusy(false); }
  };

  return (
    <>
      <h1>Invoices</h1>
      <div className={"dropzone" + (drag ? " drag" : "")}
           onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
           onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); }}
           onClick={() => input.current.click()}>
        <input ref={input} type="file" multiple hidden accept=".pdf,.jpg,.jpeg,.png,.tif,.tiff"
               onChange={(e) => { upload(e.target.files); e.target.value = ""; }} />
        {busy ? <b>Reading invoices with OCR… please wait</b> :
          <><b>Drag &amp; drop invoices here</b> or click to browse<div className="muted">PDF · JPG · PNG · TIFF — bulk upload supported (email ingestion runs via <code>manage.py ingest_emails</code>)</div></>}
      </div>
      {results && (
        <div className="card">
          {results.map((r, i) => (
            <div key={i}>{r.error ? <span className="error">✗ {r.filename}: {r.error}</span>
              : <>✓ {r.filename} → <Link to={`/invoices/${r.id}`}>#{r.id}</Link> <StatusPill s={r.status} /></>}</div>
          ))}
        </div>
      )}
      <div className="toolbar">
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUSES.map((s) => <option key={s} value={s}>{s ? s.replaceAll("_", " ") : "All statuses"}</option>)}
        </select>
        <input placeholder="Search invoice # / vendor" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} />
        <button className="btn small" onClick={load}>Search</button>
      </div>
      <div className="tablewrap"><table>
        <thead><tr><th>#</th><th>Invoice no.</th><th>Vendor</th><th>Date</th><th>PO</th><th className="r">Amount</th><th>Status</th><th>OCR</th><th>Issues</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td><Link to={`/invoices/${r.id}`}>{r.id}</Link></td><td>{r.invoice_number || <i>{r.original_filename}</i>}</td>
              <td>{r.vendor_name}</td><td>{r.invoice_date}</td><td>{r.po_number}</td><td className="r">{inr(r.total_amount)}</td>
              <td><StatusPill s={r.status} /></td><td>{r.ocr_confidence != null ? `${r.ocr_confidence}%` : "-"}</td>
              <td>{r.issue_count > 0 ? <span className="error">{r.issue_count}</span> : "-"}</td>
            </tr>
          ))}
          {!rows.length && <tr><td colSpan="9" className="muted">No invoices yet — drop some files above.</td></tr>}
        </tbody>
      </table></div>
    </>
  );
}
