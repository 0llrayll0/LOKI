import { useEffect, useState, useCallback } from "react";
import { api, ApiError, BASE } from "../lib/api";
import { Empty } from "../components/Empty";

export default function Datasets() {
  const [list, setList] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const [modalOpen, setModalOpen] = useState(false);
  const [modalDataset, setModalDataset] = useState<string | null>(null);
  const [modalVersions, setModalVersions] = useState<any[]>([]);
  const [modalVersion, setModalVersion] = useState<number | null>(null);
  const [sample, setSample] = useState<{ columns: string[]; rows: any[] } | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalErr, setModalErr] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try { setList(await api("/api/datasets/")); }
    catch (e: any) { setErr(e instanceof ApiError ? e.message : e?.message ?? "erro"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !name) return;
    setUploading(true); setErr("");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("name", name);
    if (description) fd.append("description", description);
    try {
      await fetch(BASE + "/api/datasets/upload", { method: "POST", body: fd }).then(async (r) => {
        if (!r.ok) {
          let m = `${r.status}`;
          try { const b = await r.json(); m = b?.error?.message || b?.detail || m; } catch { m = `${r.status} ${await r.text()}`; }
          throw new Error(m);
        }
      });
      setName(""); setDescription(""); setFile(null);
      await load();
    } catch (e: any) { setErr(e?.message ?? "erro"); }
    finally { setUploading(false); }
  }

  const openSample = (id: string) => {
    setModalDataset(id); setModalVersions([]); setModalVersion(null); setSample(null); setModalErr(""); setModalOpen(true);
  };
  useEffect(() => {
    if (!modalOpen || !modalDataset) return;
    let cancelled = false;
    (async () => {
      setModalLoading(true); setModalErr("");
      try {
        const d = await api<any>(`/api/datasets/${modalDataset}`);
        if (cancelled) return;
        const vs = d.versions || [];
        setModalVersions(vs);
        setModalVersion(vs.length ? vs[vs.length - 1].version : null);
      } catch (e: any) { if (!cancelled) setModalErr(e instanceof ApiError ? e.message : e?.message ?? "erro"); }
      finally { if (!cancelled) setModalLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [modalOpen, modalDataset]);
  useEffect(() => {
    if (!modalOpen || !modalDataset || modalVersion == null) return;
    let cancelled = false;
    (async () => {
      setModalLoading(true); setModalErr("");
      try {
        const s = await api<{ columns: string[]; rows: any[] }>(`/api/datasets/${modalDataset}/versions/${modalVersion}/sample?limit=20`);
        if (!cancelled) setSample(s);
      } catch (e: any) { if (!cancelled) setModalErr(e instanceof ApiError ? e.message : e?.message ?? "erro"); }
      finally { if (!cancelled) setModalLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [modalOpen, modalDataset, modalVersion]);
  useEffect(() => {
    if (!modalOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setModalOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [modalOpen]);

  return (
    <section className="card">
      <h2>Datasets</h2>
      <form className="row" onSubmit={upload}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="nome do dataset" />
        <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="descrição (opcional)" />
        <input type="file" onChange={(e) => { const f = e.target.files?.[0] || null; setFile(f); if (f && !name) setName(f.name.replace(/\.[^.]+$/, "")); }} />
        <button type="submit" disabled={uploading || !file || !name}>
          {uploading ? "enviando…" : "Enviar arquivo"}
        </button>
      </form>
      {err && <p className="err">{err}</p>}
      {loading ? <p className="muted">carregando…</p> : list.length === 0 ? <Empty title="Nenhum conjunto de dados" hint="Envie uma planilha (CSV, Excel, JSON) para começar." /> : (
        <ul className="list">
          {list.map((d: any) => (
            <li key={d.id}>
              <strong>{d.name}</strong> <span className="muted">({d.versions_count} versões)</span>
              {d.description && <span className="muted">— {d.description}</span>}
              <button className="btn-ghost btn-sm" onClick={() => openSample(d.id)} style={{ marginLeft: "auto" }}>visualizar amostra</button>
            </li>
          ))}
        </ul>
      )}
      {modalOpen && (
        <div className="modal-backdrop" onClick={() => setModalOpen(false)} role="dialog" aria-modal="true" aria-label="Amostra do dataset">
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>Amostra — {modalDataset}</h3>
              <button className="btn-ghost btn-sm" onClick={() => setModalOpen(false)} aria-label="Fechar">fechar</button>
            </div>
            {modalVersions.length > 1 && (
              <div className="row">
                <label className="muted">versão</label>
                <select value={modalVersion ?? ""} onChange={(e) => setModalVersion(Number(e.target.value))}>
                  {modalVersions.map((v: any) => <option key={v.version} value={v.version}>v{v.version}</option>)}
                </select>
              </div>
            )}
            {modalLoading && <p className="muted">carregando…</p>}
            {modalErr && <p className="err">{modalErr}</p>}
            {sample && !modalLoading && (
              <div className="table-wrap">
                <table>
                  <thead><tr>{sample.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                  <tbody>{sample.rows.map((r, i) => (<tr key={i}>{sample.columns.map((c) => <td key={c}>{String(r[c] ?? "")}</td>)}</tr>))}</tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

