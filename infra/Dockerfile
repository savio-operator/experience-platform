FROM python:3.12-slim AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home --uid 10001 backend
COPY --from=dependencies /app/.venv /app/.venv
COPY backend/app ./app
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
USER backend
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=5 \
    CMD ["/app/.venv/bin/python", "-c", "import json, urllib.request; r = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2); assert r.status == 200 and json.load(r) == {'status': 'ok'}"]
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
