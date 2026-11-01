#!/bin/sh
# Entry point do container LOKI API.
# Aplica migrations (alembic) antes de subir o uvicorn.
# Se a migration falhar, ABORTA: não sobe API com schema errado.
set -eu

echo "[entrypoint] loki-api: aplicando migrations (alembic upgrade head)..."
if ! alembic upgrade head; then
    echo "[entrypoint] ERRO: 'alembic upgrade head' falhou. Abortando o boot da API." >&2
    echo "[entrypoint] Verifique POSTGRES_* / LOKI_* e o estado do banco." >&2
    exit 1
fi
echo "[entrypoint] migrations ok. Subindo: $*"
exec "$@"
