import { useState } from "react";
import { api, ApiError } from "../lib/api";

export default function Scenario() {
  const [values, setValues] = useState("");
  const [mutations, setMutations] = useState("[]");
  const [horizon, setHorizon] = useState(7);
  const [method, setMethod] = useState("naive");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState<any>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setErr(""); setResult(null);
    const nums = values.split(/[\s,;]+/).filter(Boolean).map(Number).filter((n) => !Number.isNaN(n));
    let mut: any = [];
    try { mut = JSON.parse(mutations); } catch { setErr("mutations JSON inválido"); setLoading(false); return; }
    try { setResult(await api("/api/scenario/simulate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ values: nums, mutations: mut, horizon, method }) })); }
    catch (e: any) { setErr(e instanceof ApiError ? e.message : e?.message ?? "erro"); }
    finally { setLoading(false); }
  }

  return (
    <section className="card">
      <h2>Simulação de cenários</h2>
      <form className="row" onSubmit={run}>
        <textarea value={values} onChange={(e) => setValues(e.target.value)} placeholder="valores separados por vírgula" required style={{ flex: 1, minHeight: 80, background: "var(--bg-2)", color: "var(--ink)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: ".6rem .8rem" }} />
        <textarea value={mutations} onChange={(e) => setMutations(e.target.value)} placeholder='mutations JSON (ex: [{"type":"scale","factor":1.1}])' style={{ flex: 1, minHeight: 80, background: "var(--bg-2)", color: "var(--ink)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: ".6rem .8rem" }} />
        <input type="number" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} />
        <select value={method} onChange={(e) => setMethod(e.target.value)}><option value="naive">naive</option><option value="seasonal">seasonal</option></select>
        <button disabled={loading}>{loading ? "simulando…" : "simular"}</button>
      </form>
      {err && <p className="err">{err}</p>}
      {result && (
  <div>
    <h3>Resultado da simulação</h3>
    <ul className="list">
      {Object.entries(result).map(([k, v]) => (
        <li key={k}><strong>{k}</strong>: {typeof v === "object" ? `${Array.isArray(v) ? v.length : Object.keys(v as any).length} itens` : String(v)}</li>
      ))}
    </ul>
  </div>
)}
    </section>
  );
}