import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { Empty } from "../components/Empty";

interface Stats { datasets: number; facts: number; providers: number; health: string; }

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [ds, fk, pr, hl] = await Promise.allSettled([
          api<any[]>("/api/datasets/"),
          api<{ items: any[]; total: number }>("/api/knowledge/"),
          api<any[]>("/api/ai/providers/"),
          api<{ status: string }>("/health"),
        ]);
        if (cancelled) return;
        setStats({
          datasets: ds.status === "fulfilled" ? ds.value.length : 0,
          facts: fk.status === "fulfilled" ? fk.value.total ?? fk.value.items.length : 0,
          providers: pr.status === "fulfilled" ? pr.value.length : 0,
          health: hl.status === "fulfilled" ? hl.value.status : "indisponível",
        });
        const errors = [ds, fk, pr, hl].filter((r) => r.status === "rejected") as PromiseRejectedResult[];
        if (errors.length) setErr(errors.map((e) => (e.reason instanceof ApiError ? e.reason.message : String(e.reason))).join("; "));
      } catch (e: any) {
        if (!cancelled) setErr(e?.message ?? "erro");
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (!stats) {
    return <section className="card"><h2>Dashboard</h2>{err ? <p className="err">{err}</p> : <p className="muted">carregando…</p>}</section>;
  }

  return (
    <div className="grid">
      <div className="kpis">
        <div className="card kpi"><span className="label">datasets</span><span className="value">{stats.datasets}</span><span className="hint">cadastrados</span></div>
        <div className="card kpi"><span className="label">knowledge facts</span><span className="value">{stats.facts}</span><span className="hint">cadastrados</span></div>
        <div className="card kpi"><span className="label">providers de IA</span><span className="value">{stats.providers}</span><span className="hint">configurados</span></div>
        <div className="card kpi"><span className="label">status da API</span><span className="value">{stats.health}</span><span className="hint">/health</span></div>
      </div>
      {stats.datasets === 0 && <Empty title="Nenhum dataset ainda" hint="Envie um arquivo na aba datasets para começar." />}
      {err && <p className="err">{err}</p>}
      <ModelPanel />
    </div>
  );
}

function ModelPanel() {
  const [mode, setMode] = useState<"api" | "local">("api");
  const [model, setModel] = useState("default");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  useEffect(() => {
    (async () => {
      try {
        const d = await api<{ mode: string; model: string }>("/api/models/selector");
        setMode(d.mode as "api" | "local");
        setModel(d.model);
      } catch (e: any) { setErr(e?.message ?? "erro"); }
    })();
  }, []);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setErr(""); setOk("");
    try {
      await api("/api/models/selector", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode, model }) });
      setOk("salvo");
    } catch (e: any) { setErr(e?.message ?? "erro"); }
    finally { setSaving(false); }
  }
  return (
    <section className="card">
      <h2>Painel de modelo</h2>
      <form className="row" onSubmit={save}>
        <select value={mode} onChange={(e) => setMode(e.target.value as "api" | "local")}>
          <option value="api">API</option>
          <option value="local">Local</option>
        </select>
        <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="nome do modelo" style={{ flex: 1 }} />
        <button disabled={saving}>{saving ? "salvando…" : "aplicar"}</button>
        {ok && <span className="ok">{ok}</span>}
        {err && <span className="err">{err}</span>}
      </form>
    </section>
  );
}