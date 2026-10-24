# Experience Platform: local backend

Python 3.12, FastAPI, uv, PostgreSQL 17, Docker Compose, and GitHub Actions.
Docker Desktop's bin directory must be on PATH, including its credential helper.

## Configuration and local Docker

The application never loads `.env`. Preserve that file; use shell environment
variables instead. `.env.example` lists the settings without credentials.

Generate local-only values in a shell (do not use shell tracing or print them):

```sh
export APP_ENV=local POSTGRES_DB=experience_local
export POSTGRES_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
export OTP_HASH_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export DATABASE_URL="postgresql+psycopg://experience:${POSTGRES_PASSWORD}@127.0.0.1:55432/${POSTGRES_DB}"
```

Keep these values in your private local environment between restarts. An existing
PostgreSQL volume retains its original password; generating a new password does
not change it. Never delete an existing volume merely to fix a connection error.

From the project root:

```sh
docker compose --env-file /dev/null -f infra/compose.yml build
docker compose --env-file /dev/null -f infra/compose.yml up -d --wait db
docker compose --env-file /dev/null -f infra/compose.yml run --rm --no-deps backend /app/.venv/bin/alembic upgrade head
docker compose --env-file /dev/null -f infra/compose.yml up -d --wait --wait-timeout 60 backend
curl --fail http://127.0.0.1:8000/health
docker compose --env-file /dev/null -f infra/compose.yml down
```

Migrations are explicit, never executed automatically at application startup.
The local volume survives `down`. The API runs as a non-root user on
`127.0.0.1:8000`; PostgreSQL is published on `127.0.0.1:55432`.

For host development after starting PostgreSQL and applying migrations:

```sh
cd backend
uv sync --frozen
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

`LOG_LEVEL` defaults to `INFO`; valid values are `DEBUG`, `INFO`, `WARNING`,
`ERROR`, and `CRITICAL`. Invalid configuration fails startup without printing its
value. `APP_ENV` must explicitly be `local` or `test`. Database URLs must use
Psycopg, a local/Compose host, and the matching `experience_local` or
`experience_test` database. `OTP_HASH_KEY` must contain at least 32 bytes.
Remote database URLs, staging, and production are rejected before connecting.
This is a local-development guard, not a production security boundary against
someone modifying the code or misrepresenting an external network as localhost.

## Identity API and limitations

- `POST /auth/otp/request` accepts JSON `email`; returns 202 with a challenge UUID.
- `POST /auth/otp/verify` accepts JSON `challenge_id` and a six-digit string `code`;
  returns 204 with an opaque HttpOnly, SameSite=Strict, host-only session cookie.
- `GET /auth/me` returns the authenticated identity and database-backed roles.
- `POST /auth/logout` accepts an empty JSON object and revokes the current session.
- `GET /health` checks the running process, not the database or email delivery.

**Live email is deferred. Manual email login is not available.** Local delivery
silently discards codes. Only automated tests inject a recording delivery adapter;
that adapter is absent from the runtime image. Codes are never returned by the API
or logged. There is no fixed OTP or retrieval endpoint. Production startup is
blocked entirely; no environment switch enables real delivery or production use.

OTPs expire in five minutes, allow five failed attempts, are single-use, and are
invalidated by resends. PostgreSQL stores keyed OTP hashes and hashed session
tokens. Sessions expire after 24 hours; logout revokes them and login rotates the
current cookie. The cookie lacks Secure only for localhost HTTP. Cross-origin
mutations and form submissions are rejected; JSON is required. No CORS is enabled.
Email account identifiers are case-insensitive; dots and plus tags are preserved.

Authentication-specific PostgreSQL counters enforce these first-attempt windows:

| Operation | Limit |
|---|---|
| Send, per email | 1/minute and 5/hour |
| Send, per source IP | 20/hour |
| Verify, per source IP | 30/10 minutes, plus 5 wrong codes per challenge |
| Session lookup/logout, per source IP | 120/minute |

Rejected attempts also count. HTTP 429 includes `Retry-After`. Raw IP/email values
are not stored in throttle keys; forwarded IP headers are not trusted. Counters
are atomic across processes. Boundary bursts are possible with fixed windows;
this is deliberately not a general-purpose rate-limiting platform.

New users receive only the customer role. The migration seeds role definitions,
not privileged accounts. Role and ownership checks are separate. There is no
public role-management endpoint or ops UI. Customer profiles contain only their
identity link. Consents have a schema only: no consent is inferred from login,
no consent wording is invented, and no legal-compliance claim is made.
Minimal identity events are append-only via a PostgreSQL trigger, with no OTP,
session token, or email in the event payload. The local database owner can alter
schema and triggers; production privilege separation is not implemented here.
No retention worker, production deployment, or live provider is included.

## Tests and CI

Tests require a disposable PostgreSQL database named `experience_test` and refuse
local/production configuration. They reset identity data in that test database.
Do not point them at a database you want to preserve. SQLite is not supported.

Stop the local Compose stack first to free port 55432. In a separate shell,
generate temporary credentials as above, but set `APP_ENV=test`,
`POSTGRES_DB=experience_test`, and `COMPOSE_PROJECT_NAME=experience-tests` before
constructing `DATABASE_URL`. Then, from the project root:

```sh
docker compose --env-file /dev/null -f infra/compose.yml up -d --wait db
cd backend
uv sync --frozen
uv run --frozen alembic upgrade head
uv run --frozen alembic check
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
cd ..
# Only in the disposable experience-tests project:
docker compose --env-file /dev/null -f infra/compose.yml down --volumes
```

CI generates fresh masked credentials, starts disposable PostgreSQL, applies
migrations, runs Ruff and pytest, builds Docker, and verifies container health.

## Approved project decisions and delivery workflow

- Backend only; add architecture directories only when their implementation is needed.
- Docker configuration is under `infra/`; CI workflows are under `.github/workflows/`.
- Step 1 uses local/CI PostgreSQL only. Live email, phone OTP, managed databases,
  frontend, payments, AI, and production deployment remain deferred.
- Error tracking, type checking, and dependency auditing remain deferred.
- Preserve the existing `.env`; exclude real environment files from Git and
  Docker. Scan publishable files and all Git history before publishing. Excluding
  local `.env` does not establish that other files are clean; scanners have limits.
- After each step, verify acceptance criteria, fix failures and report actual
  changes/checks/limitations. Automatically inspect the next step in `docs/PLAN.md`
  and relevant documentation, then present a concise plan covering objective,
  essential changes, dependencies, security, verification and genuine blockers.
  Wait for authorization before implementing it; honor roadmap gates.
- Within an authorized step, make routine decisions autonomously and batch related
  changes. Ask only about material ambiguities, security, architecture, costs or
  data integrity. Avoid rereading unchanged documents and repeating successful
  checks. If the roadmap is complete, report that without inventing another step.
- Silence never authorizes another implementation step, production operations,
  paid resources or use of Render credentials.

Project documents are in `docs/`; AIRULES records the approved autonomous workflow.
Render keys and account operations require specific explicit authorization.

Step 0: Done when: app runs in Docker, CI is green, no secrets in repo.

Step 1: Done when: tests pass for auth, permissions and rate limits.


## Step 2: ops-managed vendors and catalogue

All four routes require the database-backed `ops_admin` role and retain existing
session throttling, JSON/origin checks, and secret-safe errors:

- `POST /ops/vendors`: required `name`; optional `contact_name`, `contact_email`,
  `contact_phone`, `terms_notes`.
- `PATCH /ops/vendors/{id}`: change supplied fields; nullable contact/notes fields
  can be cleared explicitly. The name cannot be blank or null.
- `POST /ops/services`: required `vendor_id` and `name`; optional `description`.
- `PATCH /ops/services/{id}`: update name/description; vendor association is immutable.

Create returns 201; update returns 200. Unknown fields/invalid input return 422;
missing records return 404 after authorization. Names are limited to 200 characters,
notes/descriptions to 4000. No-op updates do not generate an audit event. Names are
not unique identifiers; UUIDs identify records. No deletion, listing, customer
catalogue, availability, pricing or booking features are included.

Vendor/service changes and append-only audit events commit together. Audit records
contain the actor/resource UUIDs, action, changed field names and UTC timestamp,
not contact values or payload snapshots. These UUIDs remain historical references.
Existing identity events remain separate and unchanged. The local database owner
can alter triggers; these development credentials are not production credentials.

Apply migration `0002` explicitly using the existing Alembic instructions. Ops users
are supplied by test fixtures only; no automatic privileged account or login bypass
is added. Manual authentication still awaits live email delivery.

Step 2: Done when: ops can create a vendor and a service, customers cannot.
