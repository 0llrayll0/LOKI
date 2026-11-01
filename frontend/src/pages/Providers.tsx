import { useEffect, useState, useCallback } from "react";
import { api, ApiError } from "../lib/api";
import { Empty } from "../components/Empty";

interface Provider {
  id: string;
  name: string;
  type: string;
  base_url: string;
  default_model: string | null;
  has_key: boolean;
  api_key_masked: string;
  enabled: boolean;
  is_default: boolean;
  config: any;
  last_tested_at: string | null;
  last_error: string | null;
}

interface FormState {
  name: string; type: string; base_url: string; default_model: string;
  api_key: string; enabled: boolean; is_default: boolean; config: string;
}

const emptyForm: FormState = { name: "", type: "openai", base_url: "https://api.openai.com/v1", default_model: "", api_key: "", enabled: true, is_default: false, config: "{}" };

function providerStatus(p: Provider, t?: { ok: boolean }) {
  if (t) return { cls: t.ok ? "ok" : "err", label: t.ok ? "Online" : "Offline" };
  return { cls: p.enabled ? "ok" : "err", label: p.enabled ? "Ativo" : "Desativado" };
}

export default function Providers() {
  const [list, setList] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [modal, setModal] = useState<{ mode: "create" | "edit"; provider?: Provider } | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [formErr, setFormErr] = useState("");
  const [testResult, setTestResult] = useState<Record<string, { ok: boolean; message?: string | null; models: string[] }>>({});
  const [testing, setTesting] = useState<Record<string, boolean>>({});
  const [modelsOpen, setModelsOpen] = useState<Record<string, string[]>>({});
  const [loadingModels, setLoadingModels] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try { setList(await api("/api/ai/providers/")); }
    catch (e: any) { setErr(e instanceof ApiError ? e.message : e?.message ?? "erro"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  function openCreate() { setForm(emptyForm); setFormErr(""); setModal({ mode: "create" }); }
  function openEdit(p: Provider) {
    setForm({
      name: p.name, type: p.type, base_url: p.base_url, default_model: p.default_model || "",
      api_key: "", enabled: p.enabled, is_default: p.is_default,
      config: JSON.stringify(p.config || {}, null, 2),
    });
    setFormErr(""); setModal({ mode: "edit", provider: p });
  }

  async function discoverModels() {
    if (!form.base_url) { setErr("Informe o endereço antes de buscar modelos."); return; }
    setDiscovering(true); setErr("");
    try {
      const r = await api<{ ok: boolean; message: string | null; models: string[] }>("/api/ai/providers/discover", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ base_url: form.base_url, api_key: form.api_key || undefined }) });
      setModelOptions(r.models || []);
      if (r.models && r.models.length === 1 && !form.default_model) {
        setForm(f => ({ ...f, default_model: r.models[0] }));
      }
      if (!r.ok) setErr(r.message || "Não foi possível listar modelos.");
    } catch (e: any) { setErr(e instanceof ApiError ? e.message : e?.message ?? "erro"); }
    finally { setDiscovering(false); }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setFormErr("");
    let configObj: any = {};
    try { configObj = form.config.trim() ? JSON.parse(form.config) : {}; }
    catch { setFormErr("config deve ser JSON válido"); return; }
    setSaving(true);
    try {
      const payload: any = {
        name: form.name, type: form.type, base_url: form.base_url,
        default_model: form.default_model || null,
        enabled: form.enabled, is_default: form.is_default, config: configObj,
      };
      if (form.api_key.trim()) payload.api_key = form.api_key.trim();
      if (modal?.mode === "create") {
        await api("/api/ai/providers/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      } else {
        await api(`/api/ai/providers/${modal?.provider?.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      }
      setModal(null); await load();
    } catch (e: any) { setFormErr(e instanceof ApiError ? e.message : e?.message ?? "erro"); }
    finally { setSaving(false); }
  }

  async function remove(p: Provider) {
    if (!confirm(`Excluir provider ${p.name}?`)) return;
    try { await api(`/api/ai/providers/${p.id}`, { method: "DELETE" }); await load(); }
    catch (e: any) { setErr(e instanceof ApiError ? e.message : e?.message ?? "erro"); }
  }

  async function test(p: Provider) {
    setTesting((t) => ({ ...t, [p.id]: true }));
    try {
      const r = await api<{ ok: boolean; message?: string | null; models: string[] }>(`/api/ai/providers/${p.id}/test`, { method: "POST" });
      setTestResult((t) => ({ ...t, [p.id]: r }));
    } catch (e: any) {
      setTestResult((t) => ({ ...t, [p.id]: { ok: false, message: e instanceof ApiError ? e.message : e?.message ?? "erro", models: [] } }));
    } finally { setTesting((t) => ({ ...t, [p.id]: false })); }
  }

  async function loadModels(p: Provider) {
    setLoadingModels((t) => ({ ...t, [p.id]: true }));
    try {
      const r = await api<{ models: string[] }>(`/api/ai/providers/${p.id}/models`);
      setModelsOpen((t) => ({ ...t, [p.id]: r.models }));
    } catch (e: any) {
      setModelsOpen((t) => ({ ...t, [p.id]: [] }));
      setErr(e instanceof ApiError ? e.message : e?.message ?? "erro");
    } finally { setLoadingModels((t) => ({ ...t, [p.id]: false })); }
  }

  return (
    <div className="grid">
      <section className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>Provider Hub</h2>
          <button onClick={openCreate}>+ Adicionar provedor</button>
        </div>
        {err && <p className="err">{err}</p>}
        {loading ? <p className="muted">carregando…</p> : list.length === 0 ? <Empty title="Nenhum provedor cadastrado" hint="Adicione um provedor de IA para começar." action={{ label: "Adicionar provedor", onClick: openCreate }} /> : (
          <div className="provider-grid" style={{ marginTop: "1rem" }}>
            {list.map((p) => (
              <div className="card provider-card" key={p.id}>
                <div className="row" style={{ justifyContent: "space-between", marginBottom: 0 }}>
                  <strong>{p.name}</strong>
                  <span className={`badge ${providerStatus(p, testResult[p.id]).cls}`}>{providerStatus(p, testResult[p.id]).label}</span>
                </div>
                <div className="meta">{p.type} · {p.base_url}</div>
                <div className="meta">modelo padrão: {p.default_model || "—"}</div>
                <div className="meta">api key: {p.has_key ? p.api_key_masked : "sem chave"}</div>
                {p.is_default && <span className="badge">default</span>}
                {p.last_error && <span className="badge err">{p.last_error}</span>}
                {testResult[p.id] && (
                  <div className={`badge ${testResult[p.id].ok ? "ok" : "err"}`}>
                    {testResult[p.id].ok ? "conexão ok" : (testResult[p.id].message || "falhou")}
                    {testResult[p.id].models.length > 0 && ` · ${testResult[p.id].models.length} modelos`}
                  </div>
                )}
                {modelsOpen[p.id] && (
                  <ul className="list">
                    {modelsOpen[p.id].length ? modelsOpen[p.id].map((m) => <li key={m}>{m}</li>) : <li className="muted">Nenhum modelo encontrado</li>}
                  </ul>
                )}
                <div className="row" style={{ marginTop: "auto", marginBottom: 0 }}>
                  <button className="btn-ghost btn-sm" onClick={() => openEdit(p)}>editar</button>
                  <button className="btn-ghost btn-sm" disabled={testing[p.id]} onClick={() => test(p)}>{testing[p.id] ? "testando…" : "testar"}</button>
                  <button className="btn-ghost btn-sm" disabled={loadingModels[p.id]} onClick={() => loadModels(p)}>{loadingModels[p.id] ? "carregando…" : "ver modelos"}</button>
                  <button className="btn-danger btn-sm" onClick={() => remove(p)} style={{ marginLeft: "auto" }}>excluir</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {modal && (
        <div className="modal-backdrop" onClick={() => setModal(null)} role="dialog" aria-modal="true" aria-label="Provider">
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>{modal.mode === "create" ? "Adicionar provedor" : "Editar provedor"}</h3>
              <button className="btn-ghost btn-sm" onClick={() => setModal(null)}>fechar</button>
            </div>
            <p className="muted" style={{ marginTop: 0 }}>Preencha os dados do provedor. Os campos com * são obrigatórios.</p>
            <form onSubmit={submit}>
              <div className="field"><label>Nome do provedor *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required placeholder="Ex.: OpenAI principal" /></div>
              <div className="field"><label>Tipo *</label><input value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} required placeholder="openai, ollama, anthropic..." /></div>
              <div className="field"><label>Endereço (URL base) *</label><input value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} required placeholder="https://api.openai.com/v1" /></div>
              <div className="field"><label>Modelo padrão</label>
                <div className="row">
                  <input list="provider-models" value={form.default_model} onChange={(e) => setForm({ ...form, default_model: e.target.value })} placeholder="Ex.: gpt-4o-mini ou llama3" />
                  <datalist id="provider-models">{modelOptions.map((m) => <option key={m} value={m} />)}</datalist>
                  <button type="button" className="btn-ghost btn-sm" disabled={discovering} onClick={discoverModels}>{discovering ? "buscando…" : "Buscar modelos"}</button>
                </div>
                <p className="muted" style={{ marginTop: ".25rem" }}>Para Ollama use o endereço base (ex.: http://localhost:11434); o sistema detecta os modelos instalados.</p>
              </div>
              <div className="field"><label>Chave de acesso {modal.mode === "edit" && <span className="muted">(deixe vazio para manter)</span>}</label><input type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} autoComplete="off" placeholder="sk-..." /></div>
              <div className="field"><label>Configurações extras (avançado)</label><textarea value={form.config} onChange={(e) => setForm({ ...form, config: e.target.value })} placeholder="{}" /></div>
              <div className="row">
                <label><input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} /> ativo</label>
                <label><input type="checkbox" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} /> padrão</label>
              </div>
              {formErr && <p className="err">{formErr}</p>}
              <div className="row">
                <button type="submit" disabled={saving}>{saving ? "salvando…" : "salvar"}</button>
                <button type="button" className="btn-ghost" onClick={() => setModal(null)}>cancelar</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}