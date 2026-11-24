import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, inr, dt, API_ORIGIN } from "../api";
import { useUser } from "../App.jsx";
import { StatusPill } from "./Invoices.jsx";

const FIELDS = [["vendor_name_raw", "Vendor name"], ["vendor_gstin", "Vendor GSTIN"], ["invoice_number", "Invoice no."],
  ["invoice_date", "Invoice date", "date"], ["due_date", "Due date", "date"], ["po_number", "PO number"],
  ["subtotal", "Subtotal"], ["cgst", "CGST"], ["sgst", "SGST"], ["igst", "IGST"], ["total_amount", "Total"]];

export default function InvoiceDetail() {
  const { id } = useParams();
  const user = useUser();
  const [inv, setInv] = useState(null);
  const [form, setForm] = useState({});
  const [lines, setLines] = useState([]);
  const [audit, setAudit] = useState([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = async () => {
    const d = await api.get(`/invoices/${id}/`);
    setInv(d); setLines(d.lines);
    setForm(Object.fromEntries(FIELDS.map(([k]) => [k, d[k] ?? ""])));
    api.get(`/reports/audit-log/?entity_type=Invoice&entity_id=${id}`).then((r) => setAudit(r.rows || [])).catch(() => {});
  };
  useEffect(() => { load(); }, [id]);
  if (!inv) return <div>Loading…</div>;

  const editable = ["EXCEPTION", "RECEIVED"].includes(inv.status);
  const run = async (fn) => { setErr(""); setMsg(""); try { await fn(); await load(); } catch (e) { setErr(e.message); } };
  const clean = (v) => (v === "" ? null : v);
  const save = () => run(async () => {
    const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, ["subtotal","cgst","sgst","igst","total_amount"].includes(k) && v === "" ? null : clean(v)]));
    body.lines = lines.map((l) => ({ item_code: l.item_code, description: l.description, quantity: l.quantity, unit_price: l.unit_price, gst_rate: l.gst_rate, amount: l.amount }));
    await api.patch(`/invoices/${id}/`, body); setMsg("Saved. Click Re-validate to run checks again.");
  });
  const setLine = (i, k, v) => setLines(lines.map((l, j) => (j === i ? { ...l, [k]: v } : l)));
  const isImg = /\.(png|jpe?g|tiff?)$/i.test(inv.original_filename);

  return (
    <>
      <p><Link to="/invoices">← Invoices</Link></p>
      <h1>Invoice {inv.invoice_number || `#${inv.id}`} <StatusPill s={inv.status} /></h1>
      {err && <div className="error card">{err}</div>}{msg && <div className="ok card">{msg}</div>}

      {inv.issues.length > 0 && (
        <div className="card"><h3>Validation &amp; matching results</h3>
          {inv.issues.map((i) => (
            <div key={i.id} className={"issue " + i.severity}><b>{i.category}</b> {i.message}</div>
          ))}
        </div>
      )}

      <div className="grid two">
        <div className="card">
          <h3>Extracted data <small className="muted">({inv.ocr_engine}, confidence {inv.ocr_confidence}%, {inv.page_count} page(s){inv.ocr_accuracy != null && `, accuracy ${inv.ocr_accuracy}%`})</small></h3>
          <div className="form">
            {FIELDS.map(([k, label, type]) => (
              <label key={k}>{label}
                <input type={type || "text"} disabled={!editable} value={form[k] ?? ""} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></label>
            ))}
          </div>
          <div className="muted small-text">Match type: {inv.match_type_used || "n/a (no PO)"} · Source: {inv.source}</div>
          {editable && (
            <div className="actions">
              <button className="btn" onClick={save}>Save corrections</button>
              <button className="btn" onClick={() => run(async () => { await api.post(`/invoices/${id}/revalidate/`); })}>Re-validate</button>
              {user.role !== "AP_CLERK" && <button className="btn warn" onClick={() => { const c = prompt("Justification for overriding validation errors:"); if (c) run(() => api.post(`/invoices/${id}/force-submit/`, { comment: c })); }}>Override &amp; submit</button>}
              <button className="btn danger" onClick={() => { const c = prompt("Reason for rejection:"); if (c) run(() => api.post(`/invoices/${id}/reject/`, { comment: c })); }}>Reject</button>
            </div>
          )}
        </div>
        <div className="card">
          <h3>Original document</h3>
          {inv.file_url && (isImg ? <img className="preview" src={inv.file_url} alt="invoice" /> :
            <iframe className="preview" title="invoice" src={inv.file_url} />)}
        </div>
      </div>

      <div className="card"><h3>Line items (materials)</h3>
        <div className="tablewrap"><table>
          <thead><tr><th>#</th><th>Item code</th><th>Description</th><th className="r">Qty</th><th className="r">Rate</th><th className="r">GST %</th><th className="r">Amount</th></tr></thead>
          <tbody>{lines.map((l, i) => (
            <tr key={i}><td>{i + 1}</td>
              {["item_code", "description", "quantity", "unit_price", "gst_rate", "amount"].map((k) => (
                <td key={k} className={k !== "item_code" && k !== "description" ? "r" : ""}>
                  <input className="cell" disabled={!editable} value={l[k]} onChange={(e) => setLine(i, k, e.target.value)} /></td>))}
            </tr>))}</tbody>
        </table></div>
      </div>

      <div className="grid two">
        <div className="card"><h3>Approval trail</h3>
          {inv.approvals.length === 0 ? <div className="muted">Not in workflow yet</div> :
            inv.approvals.map((a) => (
              <div key={a.id} className="trail"><b>Stage {a.stage}</b> · {a.role} {a.escalated && <span className="chip warnchip">escalated</span>}
                <StatusPill s={a.status} /><div className="muted small-text">{a.decided_by ? `${a.decided_by} · ${dt(a.decided_at)}` : `due ${dt(a.due_at)}`} {a.comment && `· “${a.comment}”`}</div></div>))}
          {inv.payment && <p>Payment <b>{inv.payment.ref}</b>: <StatusPill s={inv.payment.status} /> {inv.payment.bank_reference}</p>}
        </div>
        <div className="card"><h3>Audit trail</h3>
          <div className="scroll">{audit.map((r, i) => (
            <div key={i} className="trail"><b>{r[2]}</b> <span className="muted">{r[1]} · {r[0]}</span></div>))}
            {!audit.length && <div className="muted">Audit trail visible to managers and above.</div>}</div>
        </div>
      </div>
    </>
  );
}
