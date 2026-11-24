import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, inr, dt } from "../api";
import { StatusPill } from "./Invoices.jsx";

export default function Approvals() {
  const [tasks, setTasks] = useState([]);
  const [err, setErr] = useState("");
  const load = () => api.get("/approval-tasks/?status=PENDING").then((d) => setTasks(d.results || []));
  useEffect(() => { load(); }, []);
  const decide = async (t, approve) => {
    const comment = approve ? "" : prompt("Reason for rejection:");
    if (!approve && !comment) return;
    try { await api.post(`/approval-tasks/${t.id}/decide/`, { approve, comment }); setErr(""); load(); }
    catch (e) { setErr(e.message); }
  };
  return (
    <>
      <h1>My approvals</h1>
      <p className="muted">Mobile friendly — approve or reject straight from your phone.</p>
      {err && <div className="error card">{err}</div>}
      <div className="cards">
        {tasks.map((t) => (
          <div className="card approval" key={t.id}>
            <div><b>{t.vendor_name}</b> <StatusPill s={t.status} /> {t.escalated && <span className="chip warnchip">escalated</span>}</div>
            <div>Invoice <Link to={`/invoices/${t.invoice}`}>{t.invoice_number}</Link> · Stage {t.stage} · {t.role}</div>
            <div className="big">{inr(t.amount)}</div>
            <div className="muted small-text">Due {dt(t.due_at)}</div>
            <div className="actions">
              <button className="btn ok" onClick={() => decide(t, true)}>Approve</button>
              <button className="btn danger" onClick={() => decide(t, false)}>Reject</button>
            </div>
          </div>
        ))}
        {!tasks.length && <div className="card muted">Nothing waiting for you 🎉</div>}
      </div>
    </>
  );
}
