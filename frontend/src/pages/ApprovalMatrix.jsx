import { useEffect, useState } from "react";
import { api, inr } from "../api";
import { useUser } from "../App.jsx";

const ROLES = ["MANAGER", "FINANCE_HEAD", "CFO"];

export default function ApprovalMatrix() {
  const user = useUser();
  const [rules, setRules] = useState([]);
  const [form, setForm] = useState({ name: "", min_amount: 0, max_amount: "", steps: [{ stage: 1, role: "MANAGER", sla_hours: 24, escalation_role: "FINANCE_HEAD" }] });
  const [msg, setMsg] = useState("");
  const load = () => api.get("/approval-rules/").then((d) => setRules(d.results || []));
  useEffect(() => { load(); }, []);
  const canEdit = ["FINANCE_HEAD", "CFO", "ADMIN"].includes(user.role);
  const setStep = (i, k, v) => setForm({ ...form, steps: form.steps.map((s, j) => (j === i ? { ...s, [k]: v } : s)) });
  const save = async () => {
    try {
      await api.post("/approval-rules/", { ...form, max_amount: form.max_amount === "" ? null : form.max_amount });
      setMsg("Rule saved"); load();
    } catch (e) { setMsg(e.message); }
  };
  return (
    <>
      <h1>Approval matrix</h1>
      <p className="muted">The rule whose amount range contains the invoice total is applied. Steps with the <b>same stage</b> run in parallel; stages run one after the other. Overdue tasks escalate to the escalation role.</p>
      {canEdit && <div className="toolbar"><button className="btn small" onClick={async () => setMsg(JSON.stringify(await api.post("/workflow/run-escalations/")))}>Run reminders / escalations now</button><span className="muted">{msg}</span></div>}
      <div className="cards">
        {rules.map((r) => (
          <div className="card" key={r.id}><h3>{r.name}</h3>
            <div className="muted">{inr(r.min_amount)} – {r.max_amount ? inr(r.max_amount) : "no limit"}</div>
            {r.steps.map((s) => <div key={s.id} className="trail">Stage {s.stage}: <b>{s.role}</b> · SLA {s.sla_hours}h {s.escalation_role && <>→ escalates to {s.escalation_role}</>}</div>)}
          </div>))}
      </div>
      {canEdit && (
        <div className="card"><h3>Add rule</h3>
          <div className="form">
            <label>Name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
            <label>Min amount<input type="number" value={form.min_amount} onChange={(e) => setForm({ ...form, min_amount: e.target.value })} /></label>
            <label>Max amount (blank = no limit)<input type="number" value={form.max_amount} onChange={(e) => setForm({ ...form, max_amount: e.target.value })} /></label>
          </div>
          {form.steps.map((s, i) => (
            <div className="steprow" key={i}>
              <input type="number" title="stage" value={s.stage} onChange={(e) => setStep(i, "stage", +e.target.value)} />
              <select value={s.role} onChange={(e) => setStep(i, "role", e.target.value)}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select>
              <input type="number" title="SLA hours" value={s.sla_hours} onChange={(e) => setStep(i, "sla_hours", +e.target.value)} />
              <select value={s.escalation_role} onChange={(e) => setStep(i, "escalation_role", e.target.value)}><option value="">no escalation</option>{ROLES.map((r) => <option key={r}>{r}</option>)}</select>
            </div>))}
          <div className="actions">
            <button className="btn small ghost" onClick={() => setForm({ ...form, steps: [...form.steps, { stage: 1, role: "FINANCE_HEAD", sla_hours: 24, escalation_role: "CFO" }] })}>+ step</button>
            <button className="btn small" onClick={save}>Save rule</button></div>
        </div>)}
    </>
  );
}
