# Refactoring Audit — LOKI (2026-11-01)

## Escopo executado
- Backend: Provider Hub (`/api/ai/providers`) com CRUD, criptografia de API keys, teste de conexão, listagem de modelos. Preparado para OpenAI-compatible/Ollama.
- Banco: migration 0004 (`ai_providers`) com segredo fora do DB (LOKI_SECRET_KEY).
- Frontend: redesign dark/violet com tokens centralizados, Provider Hub integrado às APIs reais, navegação acessível por abas e estados de loading/erro.
- Testes: `test_ai_providers.py` (3 passando), suíte total 115 passando; build frontend ok.

## Problemas identificados e pendências
- Motores IA (prediction/pattern/scenario/risk) ainda são baselines iniciais e requerem ampliação.
- UI ainda concentrada em `App.tsx` legado parcialmente; Iris modularizou em `src/pages`.
- Monitoramento de uso/telemetria de providers não implementado.
- Autenticação/autorização da API permanece ausente.
- Redis usage monitor não implementado.

## Decisões
- OpenAI-compatible adapter cobre múltiplos provedores sem dependência nova.
- Segredo derivado via SHA-256 + Fernet; chave em env (nunca no DB).
- SQLite compatível para testes (timestamps em Python).
