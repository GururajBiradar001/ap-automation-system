import { useEffect, useState } from "react";
import { api, inr } from "../api";

function Bars({ data, labelKey, valueKey, fmt = (v) => v }) {
  const max = Math.max(1, ...data.map((d) => d[valueKey]));
  return (
    <div className="bars">
      {data.map((d) => (
        <div className="barrow" key={d[labelKey]}>
          <span className="barlabel">{d[labelKey]}</span>
          <div className="bartrack"><div className="barfill" style={{ width: `${(d[valueKey] / max) * 100}%` }} /></div>
          <span className="barval">{fmt(d[valueKey])}</span>
        </div>
      ))}
    </div>
  );
}

const Kpi = ({ label, value, sub }) => (
  <div className="card kpi"><div className="muted">{label}</div><div className="kpival">{value}</div>{sub && <small className="muted">{sub}</small>}</div>
);

export default function Dashboard() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/dashboard/").then(setD); }, []);
  if (!d) return <div>Loading…</div>;
  const aging = Object.entries(d.aging).map(([k, v]) => ({ bucket: k, amount: v.amount, count: v.count }));
  const pay = Object.entries(d.payments).map(([k, v]) => ({ status: k, amount: v.amount, count: v.count }));
  return (
    <>
      <h1>Dashboard</h1>
      <div className="grid kpis">
        <Kpi label="Pending approvals" value={d.pending_approvals.mine} sub={`${d.pending_approvals.all} across all roles`} />
        <Kpi label="Open payables" value={inr(d.totals.open_amount)} sub={`${d.totals.invoices} invoices total`} />
        <Kpi label="Exceptions" value={d.totals.exceptions} sub="need AP review" />
        <Kpi label="OCR accuracy" value={d.ocr.accuracy_pct != null ? `${d.ocr.accuracy_pct}%` : "-"}
             sub={d.ocr.engine_confidence_pct != null ? `engine confidence ${d.ocr.engine_confidence_pct}%` : "no data yet"} />
        <Kpi label="Turnaround (to approval)" value={d.turnaround_hours.to_approval != null ? `${d.turnaround_hours.to_approval} h` : "-"} />
        <Kpi label="Turnaround (to payment)" value={d.turnaround_hours.to_payment != null ? `${d.turnaround_hours.to_payment} h` : "-"} />
      </div>
      <div className="grid two">
        <div className="card"><h3>Invoice aging (open, by due date)</h3>
          <Bars data={aging} labelKey="bucket" valueKey="amount" fmt={inr} /></div>
        <div className="card"><h3>Payment tracking</h3>
          <Bars data={pay} labelKey="status" valueKey="amount" fmt={inr} />
          <div className="muted small-text">{pay.map((p) => `${p.status}: ${p.count}`).join(" · ")}</div></div>
        <div className="card"><h3>Vendor-wise analytics (top by billed value)</h3>
          {d.vendors.length ? <Bars data={d.vendors} labelKey="name" valueKey="total" fmt={inr} /> : <div className="muted">No data yet</div>}</div>
        <div className="card"><h3>Invoices by status</h3>
          <Bars data={Object.entries(d.status_counts).map(([k, v]) => ({ s: k.replaceAll("_", " "), n: v }))} labelKey="s" valueKey="n" /></div>
      </div>
    </>
  );
}
