import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

const DEMO = ["clerk", "manager", "finance", "cfo", "admin"];

export default function Login({ onLogin }) {
  const [username, setU] = useState("clerk");
  const [password, setP] = useState("Pass@1234");
  const [err, setErr] = useState("");
  const nav = useNavigate();
  const submit = async (e) => {
    e.preventDefault();
    try {
      const r = await api.post("/auth/login/", { username, password });
      localStorage.setItem("token", r.token);
      onLogin(r.user);
      nav("/");
    } catch (ex) { setErr(ex.message); }
  };
  return (
    <div className="center">
      <form className="card login" onSubmit={submit}>
        <h2>AP Automation</h2>
        <p className="muted">Invoice capture · OCR · approvals · payments</p>
        <label>Username<input value={username} onChange={(e) => setU(e.target.value)} /></label>
        <label>Password<input type="password" value={password} onChange={(e) => setP(e.target.value)} /></label>
        {err && <div className="error">{err}</div>}
        <button className="btn" type="submit">Sign in</button>
        <div className="muted small-text">Demo users (password <code>Pass@1234</code>):
          {DEMO.map((d) => <a key={d} href="#" onClick={(e) => { e.preventDefault(); setU(d); }}> {d}</a>)}
        </div>
      </form>
    </div>
  );
}
