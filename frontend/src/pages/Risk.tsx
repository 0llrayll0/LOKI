import { useState } from "react";
import { api, ApiError } from "../lib/api";

export default function Risk() {
  const [items, setItems] = useState("[]");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState<any>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setErr(""); setResult(null);
    let arr: any = [];
    try { arr = JSON.parse(items); } catch { setErr("items JSON inválido"); setLoading(false); return; }
    try { setResult(await api("/api/risk/assess", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items: arr }) })); }
    catch (e: any) { setErr(e instanceof ApiError ? e.message : e?.message ?? "erro"); }
    finally { setLoading(false); }
  }

  return (
    <section className="card">
      <h2>Risco</h2>
      <form className="row" onSubmit={run}>
        <textarea value={items} onChange={(e) => setItems(e.target.value)} placeholder='items JSON (ex: [{"name":"x","value":1.2,"threshold":1}])' required style={{ flex: 1, minHeight: 120, background: "var(--bg-2)", color: "var(--ink)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: ".6rem .8rem" }} />
        <button disabled={loading}>{loading ? "avaliando…" : "avaliar"}</button>
      </form>
      {err && <p className="err">{err}</p>}
      {result && (
        <div className="list">
          <div className="card-row"><strong>Score</strong><span>{result.score}</span></div>
          <div className="card-row"><strong>Nível</strong><span>{result.level}</span></div>
          {result.components && <div className="muted">{JSON.stringify(result.components)}</div>}
        </div>
      )}
    </section>
  );
}