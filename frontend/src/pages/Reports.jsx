import { useEffect, useState } from "react";
import { api } from "../api";

const REPORTS = [["ap-aging", "AP aging"], ["invoice-status", "Invoice status"], ["exceptions", "Exception report"],
  ["audit-log", "Audit logs"], ["gst", "GST / tax report"]];

export default function Reports() {
  const [which, setWhich] = useState("ap-aging");
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { setData(null); setErr(""); api.get(`/reports/${which}/`).then(setData).catch((e) => setErr(e.message)); }, [which]);
  return (
    <>
      <h1>Reports</h1>
      <div className="toolbar">
        {REPORTS.map(([k, l]) => <button key={k} className={"btn small" + (which === k ? "" : " ghost")} onClick={() => setWhich(k)}>{l}</button>)}
        <div className="spacer" />
        <button className="btn small" onClick={() => api.download(`/reports/${which}/?export=csv`, `${which}.csv`)}>Export CSV</button>
      </div>
      {err && <div className="error card">{err}</div>}
      {data && <div className="tablewrap"><table>
        <thead><tr>{data.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{data.rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={typeof c === "number" ? "r" : ""}>{typeof c === "number" ? c.toLocaleString("en-IN") : String(c)}</td>)}</tr>)}
          {!data.rows.length && <tr><td colSpan={data.columns.length} className="muted">No data</td></tr>}</tbody>
      </table></div>}
    </>
  );
}
