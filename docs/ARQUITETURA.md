# LOKI — Arquitetura

Documento honesto: o que **existe de fato** hoje vs. o que é **contrato
planejado**. Nada aqui deve ser lido como "pronto" unless marcado como existe.
Status atual: **FASE 2 — Data Intelligence** (pipeline de dados + API).

## Visão geral

```
            ┌──────────────────────────────────────────────┐
            │                  LOKI CORE                    │
            │  (event bus, scheduler, config, logging)      │
            └──┬──────────┬──────────┬──────────┬──────────┘
               │          │          │          │
        ┌──────▼───┐ ┌────▼─────┐ ┌──▼──────┐ ┌─▼────────┐
        │Prediction│ │ Pattern  │ │Scenario │ │   Risk   │
        └──────────┘ └──────────┘ └─────────┘ └──────────┘
               │          │          │          │
            ┌──▼──────────▼──────────▼──────────▼──────────┐
            │               Learning                       │
            │        (feedback loop, retraining)            │
            └──────────────────────┬───────────────────────┘
                                   │
            ┌──────────────────────▼───────────────────────┐
            │              Knowledge                       │
            │   (fatos, métricas, histórico de decisões)    │
            └──────────────────────┬───────────────────────┘
                                   │
            ┌──────────────────────▼───────────────────────┐
            │           Providers (híbridos)               │
            │      (APIs, streams, batch, webhooks)        │
            └──────────────────────────────────────────────┘

Persistência: Postgres 16 (estado, knowledge) + Redis 7 (cache, filas, locks)
```

## Módulos — contrato previsto

### LOKI CORE
Núcleo transversal: registro de provedores, bus de eventos internos, scheduler
de jobs, configuração unificada via env, logging estruturado.
- Interface prevista: `core.register_provider(name, provider)`,
  `core.emit(event, payload)`, `core.on(event, handler)`.

### Prediction
Módulo de previsão de séries temporais e eventos. Recebe uma série normalizada,
retorna previsão com intervalo de confiança.
- Interface prevista: `predict(series, horizon) -> Prediction`.
- FASE 1: **não implementado**.

### Pattern
Detecção de padrões e anomalias em séries e grafos de eventos.
- Interface prevista: `detect(series) -> list[Pattern]`.
- FASE 1: **não implementado**.

### Scenario
Simulação what-if sobre modelos preditivos.
- Interface prevista: `simulate(model, inputs, mutations) -> ScenarioResult`.
- FASE 1: **não implementado**.

### Risk
Cálculo de risco agregado (probabilidade × impacto) a partir de previsões e
padrões.
- Interface prevista: `assess(signals) -> RiskScore`.
- FASE 1: **não implementado**.

### Learning
Feedback loop: consolida resultados reais vs. previstos, dispara retraining.
- Interface prevista: `record_outcome(event, actual)`, `trigger_retrain(model)`.
- FASE 1: **não implementado**.

### Knowledge
Base de conhecimento: fatos, métricas históricas, decisões tomadas e seus
resultados. Persistida em Postgres.
- Interface prevista: `query(pattern)`, `remember(fact)`.
- FASE 4: **implementado** ✅ (modelo `KnowledgeFact`, rotas `/api/knowledge`).

### Providers (híbridos)
Camada de ingestão de dados. Três tipos previstos: `ApiProvider` (pull REST),
`StreamProvider` (push, ex. WebSocket/Redis Streams), `BatchProvider`
(arquivos/DB externo). Todos implementam uma interface comum.
- Interface prevista: `Provider.fetch() -> list[Observation]`.
- FASE 1: **não implementado**.

## Data Intelligence (FASE 2) — o que existe

Pipeline de dados puro em `backend/app/data/` (sem I/O de banco, testado):

- **ingest**: lê CSV/JSON/XLSX/Parquet (sniff de separador/codificação), aplica
  `LOKI_MAX_UPLOAD_MB` e grava cópia imutável
  `{datasets_dir}/{uuid}/v{n}/original.{ext}` + sha256;
- **validate**: colunas duplicadas/ausentes, arquivo vazio ou 1 linha → `DataError`;
- **profile**: perfil por coluna + `quality_score` (JSON-safe);
- **outliers**: limites IQR por coluna numérica;
- **prepare**: limpeza opcional (`missing`, `outliers=clip`) + splits
  treino/val/teste (strategy `random` com seed fixa ou `temporal` ordenado),
  gravando `{version}/prepared/{train,val,test}.parquet` + `manifest.json`
  imutáveis; detecta vazamento (coluna idêntica ao target).

API em `backend/app/api/routes/datasets.py` (prefixo `/api/datasets`), com
schemas em `app/schemas/datasets.py` e persistência em `datasets` /
`dataset_versions` (migration `0002`):

- `POST /upload` (multipart: file, name, description) → ingestão + validação +
  profile → 201; 400 no envelope para arquivo inválido (extensão, limite, corrompido);
- `GET /` (resumo + última versão), `GET /{id}` (+ versões),
  `GET /{id}/versions/{n}` (profile, transformations, splits) → 404 no envelope;
- `POST /{id}/versions/{n}/prepare` → executa o prepare e persiste splits na
  versão; 400 se o target não existir, for constante ou houver coluna idêntica.

Segurança do upload: path montado só com o UUID gerado (o nome do arquivo nunca
vira path), whitelist de extensão e leitura em chunks com limite de tamanho.

## O que existe de fato

| Item                          | Estado        |
|-------------------------------|---------------|
| docker-compose.yml            | ✅ existe      |
| backend/Dockerfile            | ✅ existe (com entrypoint Alembic, non-root, lock) |
| .env.example / .gitignore     | ✅ existe      |
| datasets/, ml_artifacts/      | ✅ existe (datasets persiste no host via volume) |
| backend/pyproject.toml + uv.lock | ✅ existe   |
| backend/app/ (factory `create_app()`) | ✅ existe |
| Rota `GET /health`            | ✅ existe (200 ok / 503 degraded) |
| Handlers de erro (400/404/422/500 com envelope) | ✅ existe |
| backend/migrations/ (0001_initial, 0002_datasets) | ✅ existe |
| Pipeline `app/data/` (ingest, validate, profile, outliers, prepare) | ✅ existe |
| API `/api/datasets` (upload, listagem, detalhe, versão, prepare) | ✅ existe |
| backend/tests/ (pytest: health, settings, pipeline, datasets) + ruff | ✅ existe |
| Knowledge (KnowledgeFact + API `/api/knowledge`) | ✅ existe (FASE 4) |
| Qualquer módulo Prediction/Pattern/... | ❌ não implementado |

## Fases futuras (curto e honesto)

- **Fase 3:** LOKI CORE mínimo — event bus, scheduler, registro de provedores
  (`core.register_provider`/`emit`/`on`).
- **Fase 4:** Modelo de Knowledge inicial em Postgres + seed/consulta de fatos.
- **Fase 5:** Providers — ApiProvider + BatchProvider reais, registro no core e rota `/api/providers` (done).
- **Fase 6:** Prediction (baseline: SARIMA/Prophet) + Evaluation.
- **Fase 7:** Pattern (anomalia) + Risk (agregação simples).
- **Fase 8:** Scenario + Learning (loop de feedback básico).
- **Fase 9:** StreamProvider + Redis Streams como bus real.
- **Fase 10:** Hardening, testes, observabilidade, pipeline de retraining.

A FASE 1 entregou a espinha dorsal de infraestrutura e o esqueleto da API;
a FASE 2 entregou o pipeline de dados e a API de datasets. O que vem depois
(models, engines, providers) ainda é contrato, não código.
