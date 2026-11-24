import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, inr, dt } from "../api";
import { useUser } from "../App.jsx";
import { StatusPill } from "./Invoices.jsx";

export default function Payments() {
  const user = useUser();
  const [rows, setRows] = useState([]);
  const [err, setErr] = useState("");
  const load = () => api.get("/payments/").then((d) => setRows(d.results || []));
  useEffect(() => { load(); }, []);
  const canRelease = ["FINANCE_HEAD", "CFO", "ADMIN"].includes(user.role);
  const release = async (p) => { try { setErr(""); await api.post(`/payments/${p.id}/release/`); load(); } catch (e) { setErr(e.message); load(); } };
  return (
    <>
      <h1>Payments</h1>
      <p className="muted">Approved invoices automatically generate payment requests. Releasing sends the instruction to the bank gateway (mock bank in this build).</p>
      {err && <div className="error card">{err}</div>}
      <div className="tablewrap"><table>
        <thead><tr><th>Ref</th><th>Invoice</th><th>Vendor</th><th>Bank</th><th>Mode</th><th className="r">Amount</th><th>Status</th><th>UTR</th><th>Paid</th><th></th></tr></thead>
        <tbody>{rows.map((p) => (
          <tr key={p.id}><td>{p.payment_ref}</td><td><Link to={`/invoices/${p.invoice}`}>{p.invoice_number}</Link></td><td>{p.vendor_name}</td>
            <td>{p.bank_label || "-"}</td><td>{p.mode}</td><td className="r">{inr(p.amount)}</td>
            <td><StatusPill s={p.status} />{p.failure_reason && <div className="error small-text">{p.failure_reason}</div>}</td><td>{p.bank_reference}</td><td>{dt(p.paid_at)}</td>
            <td className="nowrap">
              {canRelease && ["REQUESTED", "FAILED"].includes(p.status) && <button className="btn small" onClick={() => release(p)}>Release</button>}{" "}
              <button className="btn small ghost" onClick={() => api.openBlob(`/payments/${p.id}/advice/`)}>Advice PDF</button></td></tr>))}
          {!rows.length && <tr><td colSpan="10" className="muted">No payment requests yet.</td></tr>}</tbody>
      </table></div>
    </>
  );
}
