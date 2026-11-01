FROM python:3.12-slim

# instala uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# camada de dependências: pyproject + lock (build reproduzível via lock)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# código
COPY alembic.ini ./
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY entrypoint.sh ./entrypoint.sh

# usuário não-root + permissões
RUN chmod +x /app/entrypoint.sh \
    && useradd --system --create-home --uid 10001 loki \
    && chown -R loki:loki /app

USER loki

EXPOSE 8100

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8100"]
