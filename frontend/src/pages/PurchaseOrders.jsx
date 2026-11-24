import { Fragment, useEffect, useState } from "react";
import { api, inr } from "../api";

export default function PurchaseOrders() {
  const [pos, setPos] = useState([]);
  const [grns, setGrns] = useState([]);
  const [open, setOpen] = useState(null);
  useEffect(() => {
    api.get("/purchase-orders/").then((d) => setPos(d.results || []));
    api.get("/grns/").then((d) => setGrns(d.results || []));
  }, []);
  return (
    <>
      <h1>Purchase orders &amp; goods receipts</h1>
      <p className="muted">Reference data used for 2-way (PO ↔ Invoice) and 3-way (PO ↔ GRN ↔ Invoice) matching. Created through the API / admin (ERP integration point).</p>
      <div className="tablewrap"><table>
        <thead><tr><th>PO</th><th>Vendor</th><th>Date</th><th>Match type</th><th className="r">Value</th></tr></thead>
        <tbody>{pos.map((p) => (<Fragment key={p.id}>
          <tr className="clickable" onClick={() => setOpen(open === p.id ? null : p.id)}>
            <td>{p.po_number}</td><td>{p.vendor_name}</td><td>{p.po_date}</td><td>{p.match_type}</td><td className="r">{inr(p.total)}</td></tr>
          {open === p.id && <tr><td colSpan="5">
            <table className="inner"><thead><tr><th>Item</th><th>Description</th><th className="r">Ordered</th><th className="r">Received (GRN)</th><th className="r">Price</th></tr></thead>
              <tbody>{p.lines.slice(0, 12).map((l) => <tr key={l.id}><td>{l.item_code}</td><td>{l.description}</td><td className="r">{l.quantity}</td><td className="r">{l.received_qty}</td><td className="r">{l.unit_price}</td></tr>)}</tbody></table>
          </td></tr>}</Fragment>))}</tbody>
      </table></div>
      <h3>Goods receipts (GRN)</h3>
      <div className="tablewrap"><table>
        <thead><tr><th>GRN</th><th>PO</th><th>Date</th><th>Lines</th></tr></thead>
        <tbody>{grns.map((g) => <tr key={g.id}><td>{g.grn_number}</td><td>{g.po_number}</td><td>{g.received_date}</td><td>{g.lines.length}</td></tr>)}</tbody>
      </table></div>
    </>
  );
}
