import { useEffect, useState } from "react";
import { api } from "../api";
import { useUser } from "../App.jsx";
import { StatusPill } from "./Invoices.jsx";

const empty = { name: "", gstin: "", email: "", phone: "", address: "", payment_terms_days: 30 };
const emptyBank = { account_name: "", account_number: "", ifsc: "", bank_name: "", branch: "" };

export default function Vendors() {
  const user = useUser();
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(empty);
  const [gst, setGst] = useState(null);
  const [sel, setSel] = useState(null);
  const [bank, setBank] = useState(emptyBank);
  const [err, setErr] = useState("");
  const load = () => api.get("/vendors/").then((d) => { setRows(d.results || []); if (sel) setSel((d.results || []).find((v) => v.id === sel.id)); });
  useEffect(() => { load(); }, []);
  const run = async (fn) => { setErr(""); try { await fn(); await load(); } catch (e) { setErr(e.message); } };
  const checkGst = async (v) => { setForm({ ...form, gstin: v.toUpperCase() }); if (v.length === 15) setGst(await api.post("/vendors/validate-gstin/", { gstin: v.toUpperCase() })); else setGst(null); };
  const canApprove = ["MANAGER", "FINANCE_HEAD", "CFO", "ADMIN"].includes(user.role);

  return (
    <>
      <h1>Vendor management</h1>
      {err && <div className="error card">{err}</div>}
      <div className="grid two">
        <div className="card"><h3>New vendor (onboarding)</h3>
          <div className="form">
            <label>Name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
            <label>GSTIN<input value={form.gstin} maxLength={15} onChange={(e) => checkGst(e.target.value)} />
              {gst && <small className={gst.valid ? "okt" : "error"}>{gst.valid ? "✓ valid GSTIN" : gst.message}</small>}</label>
            <label>Email<input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
            <label>Phone<input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></label>
            <label>Payment terms (days)<input type="number" value={form.payment_terms_days} onChange={(e) => setForm({ ...form, payment_terms_days: e.target.value })} /></label>
          </div>
          <button className="btn" onClick={() => run(async () => { await api.post("/vendors/", form); setForm(empty); setGst(null); })}>Create vendor (draft)</button>
        </div>

        {sel && (
          <div className="card"><h3>{sel.code} · {sel.name} <StatusPill s={sel.status} /></h3>
            <div className="muted">GSTIN {sel.gstin} · PAN {sel.pan} · State {sel.state_code}</div>
            <h4>Bank accounts</h4>
            {sel.banks.map((b) => <div key={b.id}>{b.bank_name} ****{b.account_number.slice(-4)} · {b.ifsc} {b.is_verified ? <span className="okt">✓ verified</span> : <span className="muted">unverified</span>}</div>)}
            <div className="form">
              {[["account_name", "Account holder"], ["account_number", "Account no."], ["ifsc", "IFSC"], ["bank_name", "Bank"]].map(([k, l]) => (
                <label key={k}>{l}<input value={bank[k]} onChange={(e) => setBank({ ...bank, [k]: e.target.value })} /></label>))}
            </div>
            <div className="actions">
              <button className="btn small" onClick={() => run(async () => { await api.post("/vendor-banks/", { ...bank, vendor: sel.id, is_primary: !sel.banks.length }); setBank(emptyBank); })}>Add bank account</button>
              {["DRAFT", "REJECTED"].includes(sel.status) && <button className="btn small" onClick={() => run(() => api.post(`/vendors/${sel.id}/submit/`))}>Submit for approval</button>}
              {sel.status === "PENDING_APPROVAL" && canApprove && <>
                <button className="btn small ok" onClick={() => run(() => api.post(`/vendors/${sel.id}/decide/`, { approve: true }))}>Approve vendor</button>
                <button className="btn small danger" onClick={() => run(() => api.post(`/vendors/${sel.id}/decide/`, { approve: false, comment: prompt("Reason?") || "" }))}>Reject</button></>}
            </div>
          </div>
        )}
      </div>
      <div className="tablewrap"><table>
        <thead><tr><th>Code</th><th>Name</th><th>GSTIN</th><th>Terms</th><th>Banks</th><th>Status</th></tr></thead>
        <tbody>{rows.map((v) => (
          <tr key={v.id} className="clickable" onClick={() => setSel(v)}>
            <td>{v.code}</td><td>{v.name}</td><td>{v.gstin}</td><td>{v.payment_terms_days}d</td><td>{v.banks.length}</td><td><StatusPill s={v.status} /></td></tr>))}</tbody>
      </table></div>
    </>
  );
}
