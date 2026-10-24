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


## Step 3: inventory and holds

Ops-only routes under `/ops/inventory` reuse existing authentication and throttling:

- `POST /slots`: service UUID, timezone-aware `starts_at`, `ends_at`, `release_at`,
  and positive integer `capacity`. New slots start UNKNOWN. Windows for the same
  service cannot overlap; times and capacity are immutable in this step.
- `GET /slots/{id}`: current state, held quantity and available quantity.
- `PATCH /slots/{id}/availability`: `state` UNKNOWN, AVAILABLE_UNVERIFIED,
  AVAILABLE_VERIFIED or UNAVAILABLE. Verification requires `verified_until`.
- `POST /slots/{id}/holds`: positive `quantity`, `expires_at`, UUID
  `idempotency_key`. Repeating the same request returns the original hold;
  reusing its key with different values or another actor returns 409.
- `POST /holds/{id}/release` and `POST /slots/{id}/refresh`: send `{}`.

Only fresh verified capacity can be held. Hold expiry cannot exceed verification
or release deadlines. PostgreSQL row locks serialize capacity checks and updates;
mutation and audit records commit together. Expired holds stop consuming capacity
immediately in reads and allocation; a later mutation or explicit refresh persists
expiry events. No background worker is required. Release is idempotent. Booking
states are reserved vocabulary, not implemented booking operations.

Apply migration `0003` explicitly. Its downgrade removes inventory tables but keeps
the expanded audit vocabulary to preserve historical audit events. Capacity is
independent per service: shared physical resources across services are not modeled.
No real vendor agreement exists yet. Development remains local/CI only; real inventory requires agreed capacity, freshness and release
terms and validation of shared-resource assumptions before pilot use. All deadlines
are explicit ops inputs; no vendor availability or terms are inferred.

Step 3: Done when: concurrent hold tests prove no double-booking.


## Step 4: intent parsing (live provider disabled)

`POST /intents/parse` accepts `{"text": "date tonight, Rs 3000, no alcohol"}`
with an authenticated session and existing JSON/origin protections. It is limited
to 10 attempts per user and 20 per IP per minute, in addition to session limits.
The shipped adapter always returns 503 `AI provider disabled`. There is no live
adapter, API-key lookup, paid call, or environment switch to enable one. Tests inject
deterministic providers; they do not prove real-model extraction quality.

The provider contract separates fixed instructions, untrusted text, and the output
schema. Valid output contains nullable `kind` (now_or_tonight, date,
birthday_or_surprise), `when_text`, `party_size`, `budget_paise`, and a bounded list
of `constraints`. All fields are required in provider JSON; unspecified scalar
values must be null. `missing_fields` identifies absent kind, time, party size and
budget for clarification, not booking eligibility. Time wording stays unresolved;
no dates, prices or availability are inferred. Constraints remain untrusted data.
Schema checks prevent invalid structure, not all semantically incorrect extraction.

Unknown fields, duplicate JSON keys, coerced types, invalid bounds, malformed or
oversized responses are rejected with 502; provider failures/timeouts return 503.
Calls have a five-second timeout and no automatic retries. No tools or database
write capabilities are passed to providers. Requests/results are not persisted.
Numeric input/output token counts and cost in INR paise are returned/logged with
request ID when supplied authoritatively; unknown values stay null, never assumed
zero. Raw text, outputs, credentials and exception details are not logged.
No new dependencies or migrations are needed. Provider selection, live usage,
verified pricing and real-model evaluation remain deferred pending authorization.

Step 4: Done when: sample requests become valid structured intents; bad output is rejected.


## Step 5: constraints and pricing

`app.modules.pricing.service.evaluate` is an internal, side-effect-free rules
boundary for subsequent options generation; it is not a customer pricing API.
It requires explicit components, fees, taxes, budget and minimum margin. Components
carry service UUID, quantity, unit selling price and unit cost; fees carry separate
charge/cost amounts. All amounts are integer INR paise. Taxes are explicit
pass-through collected amounts excluded from margin; no tax rates, jurisdiction
rules, deductions, fee policies or minimum margins are inferred. Empty fees/taxes
must be explicitly supplied. Missing or invalid prices/costs are validation errors.

Hard/soft requirements support exact equality and integer bounds. Facts need a
source UUID and a future verification deadline. Missing, expired or incompatible
facts cannot satisfy a hard requirement. Soft results remain visible without
rejecting the candidate. Budget and margin pass/fail are independent; final
acceptance requires both and every hard requirement. Negative margins are reported
as losses and fail a nonnegative explicitly supplied margin threshold. Totals beyond
the supported safe integer range are rejected rather than rounded or truncated.

Callers must obtain evidence and prices from trusted server-side sources, resolve
all mandatory free-text constraints, and supply the server clock. A UUID alone is
not proof of vendor verification. This pure evaluator does not authenticate evidence
or determine tax applicability. No endpoint accepts client/model assertions as facts.
Real prices, policy and tax inputs remain unavailable; tests use synthetic data only.

Step 5: Done when: plans violating hard constraints never pass.
