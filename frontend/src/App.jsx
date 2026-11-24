import { useEffect, useState, createContext, useContext } from "react";
import { Navigate, NavLink, Route, Routes, Outlet, useNavigate } from "react-router-dom";
import { api, getToken, dt } from "./api";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Invoices from "./pages/Invoices.jsx";
import InvoiceDetail from "./pages/InvoiceDetail.jsx";
import Approvals from "./pages/Approvals.jsx";
import Vendors from "./pages/Vendors.jsx";
import PurchaseOrders from "./pages/PurchaseOrders.jsx";
import Payments from "./pages/Payments.jsx";
import Reports from "./pages/Reports.jsx";
import ApprovalMatrix from "./pages/ApprovalMatrix.jsx";

export const UserCtx = createContext(null);
export const useUser = () => useContext(UserCtx);

const NAV = [
  ["/", "Dashboard"], ["/invoices", "Invoices"], ["/approvals", "My Approvals"],
  ["/vendors", "Vendors"], ["/purchase-orders", "PO & GRN"], ["/payments", "Payments"],
  ["/reports", "Reports"], ["/approval-matrix", "Approval Matrix"],
];

function Layout() {
  const user = useUser();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState([]);
  const [showNotes, setShowNotes] = useState(false);

  useEffect(() => {
    const load = () => api.get("/notifications/").then((d) => setNotes(d.results || [])).catch(() => {});
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  const logout = () => { localStorage.clear(); nav("/login"); window.location.reload(); };
  return (
    <div className="shell">
      <aside className={"sidebar" + (open ? " open" : "")} onClick={() => setOpen(false)}>
        <div className="brand">AP<span>Automation</span></div>
        {NAV.map(([to, label]) => (
          <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => "navlink" + (isActive ? " active" : "")}>{label}</NavLink>
        ))}
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="burger" onClick={() => setOpen(!open)}>☰</button>
          <div className="spacer" />
          <div className="bell" onClick={() => setShowNotes(!showNotes)}>
            🔔{notes.filter((n) => !n.is_read).length > 0 && <b className="badge">{notes.filter((n) => !n.is_read).length}</b>}
          </div>
          <div className="who">{user.username} <span className="chip">{user.role}</span></div>
          <button className="btn small ghost" onClick={logout}>Logout</button>
          {showNotes && (
            <div className="notes">
              {notes.length === 0 && <div className="muted pad">No notifications</div>}
              {notes.slice(0, 15).map((n) => (
                <div key={n.id} className="note" onClick={() => { setShowNotes(false); if (n.link) nav(n.link); }}>
                  <b>{n.title}</b><div className="muted">{n.body}</div><small>{dt(n.created_at)}</small>
                </div>
              ))}
            </div>
          )}
        </header>
        <main className="content"><Outlet /></main>
      </div>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(!getToken());
  useEffect(() => {
    if (getToken()) api.get("/auth/me/").then(setUser).catch(() => localStorage.clear()).finally(() => setReady(true));
  }, []);
  if (!ready) return <div className="center">Loading…</div>;
  return (
    <UserCtx.Provider value={user}>
      <Routes>
        <Route path="/login" element={<Login onLogin={setUser} />} />
        <Route element={user ? <Layout /> : <Navigate to="/login" />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/invoices" element={<Invoices />} />
          <Route path="/invoices/:id" element={<InvoiceDetail />} />
          <Route path="/approvals" element={<Approvals />} />
          <Route path="/vendors" element={<Vendors />} />
          <Route path="/purchase-orders" element={<PurchaseOrders />} />
          <Route path="/payments" element={<Payments />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/approval-matrix" element={<ApprovalMatrix />} />
        </Route>
      </Routes>
    </UserCtx.Provider>
  );
}
