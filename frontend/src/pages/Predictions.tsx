import { useState } from "react";
import { api, ApiError } from "../lib/api";

type Result = { forecast: number[]; lower: number[]; upper: number[]; metrics: Record<string, number>; horizon: number };

export default function Predictions() {
  const [datasetId, setDatasetId] = useState("");
  const [targetCol, setTargetCol] = useState("");
  const [horizon, setHorizon] = useState(7);
  const [method, setMethod] = useState("naive");
  const [version, setVersion] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState<Result | null>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setErr(""); setResult(null);
    const qs = new URLSearchParams({ dataset_id: datasetId, target_col: targetCol, horizon: String(horizon), method });
    if (version) qs.set("version", version);
    try {
      const r = await api<Result>(`/api/predictions/?${qs.toString()}`);
      setResult(r);
    } catch (e: any) { setErr(e instanceof ApiError ? e.message : e?.message ?? "erro"); }
    finally { setLoading(false); }
  }

  return (
    <div className="grid">
      <section className="card">
        <h2>Prever o futuro dos seus dados</h2>
        <p className="muted" style={{ marginTop: 0 }}>Selecione o conjunto de dados, a coluna alvo e por quantos dias deseja prever.</p>
        <form className="row" onSubmit={run}>
          <input value={datasetId} onChange={(e) => setDatasetId(e.target.value)} placeholder="Identificador do conjunto de dados" required style={{ flex: 1 }} />
          <input value={targetCol} onChange={(e) => setTargetCol(e.target.value)} placeholder="Coluna que deseja prever" required />
          <input type="number" min={1} max={60} value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} title="Quantos valores prever" />
          <select value={method} onChange={(e) => setMethod(e.target.value)} title="Método">
            <option value="naive">simples</option>
            <option value="seasonal">sazonal</option>
            <option value="moving_average">média móvel</option>
          </select>
          <input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="versão (opcional)" />
          <button disabled={loading}>{loading ? "calculando…" : "Prever"}</button>
        </form>
        {err && <p className="err">{err}</p>}
      </section>
      {result && (
        <section className="card">
          <h2>Resultado da previsão</h2>
          <p className="muted">Foram previstos {result.forecast.length} valores.</p>
          <ul className="list">
            {result.forecast.map((v, i) => (
              <li key={i}>
                <span className="muted">Dia {i + 1}</span>
                <strong>{Number(v).toFixed(4)}</strong>
                <span className="muted">(faixa: {Number(result.lower[i]).toFixed(4)} a {Number(result.upper[i]).toFixed(4)})</span>
              </li>
            ))}
          </ul>
          {result.metrics && Object.keys(result.metrics).length > 0 && (
            <div style={{ marginTop: 12 }}>
              <h3>Qualidade da previsão</h3>
              <ul className="list">
                {Object.entries(result.metrics).map(([k, v]) => (
                  <li key={k}><strong>{k}</strong>: {Number(v).toFixed(4)}</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}