import { useEffect, useState, useCallback } from "react";
import { api, ApiError } from "../lib/api";
import { Empty } from "../components/Empty";

export default function Knowledge() {
  const [list, setList] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [tags, setTags] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const qs = tagFilter ? `?tag=${encodeURIComponent(tagFilter)}` : "";
      const r = await api<{ items: any[]; total: number }>("/api/knowledge/" + qs);
      setList(r.items);
    } catch (e: any) { setErr(e instanceof ApiError ? e.message : e?.message ?? "erro"); }
    finally { setLoading(false); }
  }, [tagFilter]);
  useEffect(() => { load(); }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      let parsedValue: unknown = value;
      try { parsedValue = JSON.parse(value); } catch { /* keep string */ }
      await api("/api/knowledge/", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key, value: parsedValue, tags: tags.split(",").map((t) => t.trim()).filter(Boolean) }),
      });
      setKey(""); setValue(""); setTags("");
      await load();
    } catch (e: any) { setErr(e instanceof ApiError ? e.message : e?.message ?? "erro"); }
  }

  async function remove(id: string) {
    if (!confirm("Excluir fato?")) return;
    try { await api(`/api/knowledge/${id}`, { method: "DELETE" }); await load(); }
    catch (e: any) { setErr(e instanceof ApiError ? e.message : e?.message ?? "erro"); }
  }

  async function doSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!search) { load(); return; }
    setLoading(true); setErr("");
    try {
      const r = await api<{ items: any[]; total: number }>(`/api/knowledge/search?q=${encodeURIComponent(search)}`);
      setList(r.items);
    } catch (e: any) { setErr(e instanceof ApiError ? e.message : e?.message ?? "erro"); }
    finally { setLoading(false); }
  }

  return (
    <div className="grid">
      <section className="card">
        <h2>Novo fato</h2>
        <form className="row" onSubmit={create}>
          <input value={key} onChange={(e) => setKey(e.target.value)} placeholder="key" required />
          <input value={value} onChange={(e) => setValue(e.target.value)} placeholder='value (texto ou JSON)' required style={{ flex: 1 }} />
          <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="tags (csv)" />
          <button>criar</button>
        </form>
        {err && <p className="err">{err}</p>}
      </section>
      <section className="card">
        <h2>Knowledge Facts</h2>
        <form className="row" onSubmit={doSearch}>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="buscar por key" />
          <input value={tagFilter} onChange={(e) => setTagFilter(e.target.value)} placeholder="filtrar por tag" />
          <button className="btn-ghost" type="button" onClick={() => { setSearch(""); setTagFilter(""); load(); }}>limpar</button>
          <button type="submit">buscar</button>
        </form>
        {loading ? <p className="muted">carregando…</p> : list.length === 0 ? <Empty title="Nenhum fato" hint="Cadastre um fato acima." /> : (
          <ul className="list">
            {list.map((f: any) => (
              <li key={f.id}>
                <div style={{ flex: 1 }}>
                  <code className="code">{f.key}</code>: {typeof f.value === "object" ? JSON.stringify(f.value) : String(f.value)}
                  <div className="muted">{f.tags?.join(", ")}{f.source ? ` · ${f.source}` : ""}</div>
                </div>
                <button className="btn-danger btn-sm" onClick={() => remove(f.id)}>excluir</button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}