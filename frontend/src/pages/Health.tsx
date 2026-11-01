import { useEffect, useState, useCallback } from "react";
import { api, ApiError } from "../lib/api";

export default function Health() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try { setData(await api("/health")); }
    catch (e: any) { setErr(e instanceof ApiError ? e.message : e?.message ?? "erro"); setData(null); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  const ok = data && (data.status === "ok" || data.status === "healthy");
  return (
    <section className="card">
      <h2>Saúde do sistema</h2>
      {loading && <p className="muted">verificando…</p>}
      {err && <p className="err">{err}</p>}
      {data && (
        <div className="kpi">
          <span className={`badge ${ok ? "ok" : "err"}`}>{ok ? "Online" : "Offline"}</span>
          <span className="muted">Serviço: {data.service || "—"}</span>
          {data.version && <span className="muted">Versão: {data.version}</span>}
        </div>
      )}
      <div className="row" style={{ marginTop: 12 }}>
        <button onClick={load}>verificar novamente</button>
      </div>
    </section>
  );
}