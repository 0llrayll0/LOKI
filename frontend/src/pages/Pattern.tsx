import { useState } from "react";
import { api, ApiError } from "../lib/api";

export default function Pattern() {
  const [values, setValues] = useState("");
  const [method, setMethod] = useState("zscore");
  const [threshold, setThreshold] = useState(3);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState<any>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setErr(""); setResult(null);
    const nums = values.split(/[\s,;]+/).filter(Boolean).map(Number).filter((n) => !Number.isNaN(n));
    try { setResult(await api("/api/pattern/detect", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ values: nums, method, threshold }) })); }
    catch (e: any) { setErr(e instanceof ApiError ? e.message : e?.message ?? "erro"); }
    finally { setLoading(false); }
  }

  return (
    <section className="card">
      <h2>Detecção de padrões</h2>
      <form className="row" onSubmit={run}>
        <textarea value={values} onChange={(e) => setValues(e.target.value)} placeholder="valores separados por vírgula" required style={{ flex: 1, minHeight: 80, background: "var(--bg-2)", color: "var(--ink)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: ".6rem .8rem" }} />
        <select value={method} onChange={(e) => setMethod(e.target.value)}><option value="zscore">zscore</option></select>
        <input type="number" value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} />
        <button disabled={loading}>{loading ? "detectando…" : "detectar"}</button>
      </form>
      {err && <p className="err">{err}</p>}
      {result && (
  <div>
    <h3>Padrões encontrados</h3>
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