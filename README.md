# Experience Platform: backend foundation

Requires Python 3.12, uv, and Docker with Compose. If Docker is not on PATH,
use the CLI inside Docker Desktop or add its bin directory to your shell PATH.

## Local development

```sh
cd backend
uv sync --frozen
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

`GET /health` returns `{"status":"ok"}` and an `X-Request-ID` header.
It checks the running process only, not production readiness or dependencies.

The only configuration is `LOG_LEVEL`, defaulting to `INFO`. Supported values:
`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Invalid values prevent startup
without printing the supplied value. Set this variable in the process environment.
The application does not load `.env`; `.env.example` is documentation only.

## Docker

From the project root:

```sh
docker compose --env-file /dev/null -f infra/compose.yml build
docker compose --env-file /dev/null -f infra/compose.yml up -d --wait --wait-timeout 60
curl --fail http://127.0.0.1:8000/health
docker compose --env-file /dev/null -f infra/compose.yml down
```

The service runs as a non-root user and binds only to localhost. Compose uses
`LOG_LEVEL=INFO`; `--env-file /dev/null` prevents loading a local environment file.
Never add real environment files to Git or the Docker build context.

## Checks

From `backend/`:

```sh
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

GitHub Actions runs these checks, builds the image, and verifies container health.

## Approved Step 0 decisions

- Backend only: Python 3.12, FastAPI, uv, Docker, and GitHub Actions.
- Create architecture directories only when their implementation is needed.
- CI workflows live in `.github/workflows/`; Docker configuration lives in `infra/`.
- Standard Python logging records request IDs and status, without request data.
- Error tracking, type checking, dependency auditing, domain modules, and all
  integrations are deferred. No cloud deployment or extra services in Step 0.
- The existing `.env` is intentional local-only configuration, excluded from
  publishable-file scanning, Git, and Docker. Scan every publishable file and
  all available history before publishing; a clean scan is not a guarantee that
  every possible secret has been detected.

Original project documents are preserved in `docs/`.

Done when: app runs in Docker, CI is green, no secrets in repo.
