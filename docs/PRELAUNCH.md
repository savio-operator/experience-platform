# Pre-launch checklist — Step 11

Status: local hardening only. Not production-ready. The roadmap acceptance criterion
remains: **Done when: pre-launch checklist is complete.** Unchecked items below are
real blockers, not implicitly approved exceptions. No cloud resources, live providers,
production connections or Render operations are enabled by this work.

## Local controls reviewed

- [x] Local/test-only configuration rejects production and non-local database URLs;
  real `.env` files are excluded from Git and Docker. No implicit dotenv loading.
- [x] OTP codes and session tokens are hashed; OTP expiry, retry bounds, resend
  invalidation, logout revocation, role checks and resource ownership have tests.
- [x] JSON/origin checks protect mutations; responses use `no-store` and generated
  request IDs. Application logs omit request bodies and sensitive error details;
  Docker disables Uvicorn access logging and proxy-header trust.
- [x] Booking/hold locks, idempotency, confirmation evidence, separate payment states,
  notification eligibility and atomic case audits are tested. Case closure cannot
  record refunds or erase outstanding financial work.
- [x] Explicit migrations, non-root backend container, localhost published ports,
  locked dependencies, pinned existing GitHub Actions, and CI quality gates retained.
- [x] Added locked development-only `pip-audit` with strict failure behavior in CI.
  It audits installed packages, including transitive/runtime and development packages.
  No ignores or automatic fixes. Advisory outages fail CI; rerun after recovery.
  Package names/versions are sent to the public advisory service; application data,
  `.env` and credentials are not inputs. This is known-advisory scanning, not malware,
  OS/container scanning, a penetration test or proof of absence of vulnerabilities.
  See [pip-audit documentation](https://github.com/pypa/pip-audit).
- [x] Added local backup/restore and bounded load checks to CI (commands below).
- [ ] Verify these new CI gates on GitHub after an authorized push. Local execution
  does not establish that remote CI has passed.

## Repeatable disposable checks

Use the existing README setup with generated **disposable** test credentials exported
explicitly, `APP_ENV=test`, `POSTGRES_DB=experience_test`, and matching local
`DATABASE_URL`. Never source the real `.env`. Start/migrate/test the Compose project
before running recovery; stop API workers and concurrent writers during recovery.
From `backend/`:

```sh
uv sync --frozen
uv run --frozen pip-audit --strict --progress-spinner off
uv run --frozen python -m tools.recovery --project experience-step11-check
uv run --frozen python -m tools.load_smoke
```

Recovery uses the named project's `db` container and PostgreSQL's own `pg_dump` and
`pg_restore`. It requires test configuration, inserts a synthetic user marker, dumps
`experience_test`, restores to a newly created random `experience_restore_*` database,
compares row counts and content digests for every public table, then verifies restored
foreign-key and audit protection. Source changes cause a mismatch, not a false pass.
Backup bytes stay in the disposable container; commands suppress potentially sensitive
error output. It drops only the database it successfully created and removes its dump
in a `finally` block. It does not delete the source database or rewrite migrations.
An interrupted process/container can leave temporary resources: remove only this
explicitly disposable Compose project with `down --volumes` after verification.
This tests logical recovery, not offsite storage, encryption, disaster recovery time,
point-in-time recovery or a production RPO/RTO. The synthetic marker stays in the
source test database until normal disposable cleanup.

Load smoke targets HTTP `127.0.0.1` only, requires test mode, disables proxies and
redirects, sends 80 requests with eight workers and five-second request timeouts:
60 health checks and 20 unauthenticated ops requests. It checks expected JSON/status,
request IDs and cache protection, and reports measured p95/max latency. It exercises
DB-backed authentication rejection but not authenticated checkout capacity, sustained
traffic or production latency guarantees. Repeated runs may correctly hit the existing
session throttle; wait for its window to reset rather than weaken it.

## Staging and operational recommendations — not provisioned

- [ ] Approve hosting, region, budget, operators and access controls before provisioning.
  Keep one backend and PostgreSQL; separate staging credentials, database, domain and
  provider accounts from production. Use synthetic data; do not clone production PII.
- [ ] Implement an explicitly reviewed staging configuration. Current runtime rejects
  staging/production; do not bypass that gate by setting `APP_ENV=local` in the cloud.
  Require HTTPS, Secure cookies, exact allowed origins/hosts, trusted proxy boundaries,
  request size limits, and correctly attributed client IP rate limits. Existing HTTP
  cookies and localhost origins are deliberately local-only.
- [ ] Separate migration-owner privileges from least-privilege runtime DB privileges.
  Local Compose's database owner can alter tables/triggers; append-only triggers alone
  do not protect against an owner. Restrict DB network access and privileged ops access.
- [ ] Approve monitoring processor/region, data retention and operator access before
  adding an SDK. Prefer an allowlist of error category, deployment version, request ID,
  route template and timestamp. Exclude raw URLs, headers/cookies, bodies, emails,
  OTPs, tokens, financial details and local variables. Verify redaction with synthetic
  sentinels before enabling export; no telemetry is sent in this step.
- [ ] Agree alert owner, escalation channel and thresholds. Candidate signals: 5xx/DB
  failures, unavailable health/readiness, payment review backlog, expired bookings,
  exhausted notifications, failed jobs and stale backups. Avoid sensitive alert content;
  link to authenticated ops views. Test delivery/acknowledgement and a recovery drill.
- [ ] Define DB-aware readiness separately from current process-only `/health`, deploy
  rollback procedure, job scheduling/recovery, backup encryption/access, offsite storage,
  retention, and recovery objectives. Test restores using approved staging infrastructure.
- [ ] Scan the deployed image/base packages and review dependency findings regularly.
  Local Python package scanning does not cover the OS. Approve sustained-load scenarios
  and measurable service targets before making capacity claims.

## Consent and deletion review — implementation deferred

Current storage has customers linked to users and consent rows with purpose, version,
granted flag and timestamp. Signup creates a customer, **not consent**. There is no
approved consent catalogue/text, consent API, withdrawal enforcement, access/export or
deletion workflow. Do not treat the schema as compliant behavior or imply consent.

- [ ] Approve purpose-specific wording/versions, which processing requires consent,
  how withdrawal affects delivery, and how evidence of the displayed notice is retained.
- [ ] Establish applicable privacy obligations with qualified review. No legal deadlines,
  age rules or retention periods are asserted here; this document is not a DPDP
  compliance determination.
- [ ] Decide retention/deletion treatment for email, OTP challenges, sessions, customer
  profiles, consents, booking/payment records, vendor contacts, case notes/evidence,
  notification records, identity events and immutable audits; include backups and future
  processors. Financial disputes and evidence obligations need explicit decisions.
- [ ] Design authenticated requests, identity verification, session revocation, pending
  booking/payment holds on processing, review/approval, idempotent execution and truthful
  request status. Do not promise immediate erasure while obligations remain unresolved.
- [ ] Preserve relational integrity and audit obligations. User-linked foreign keys and
  historical identifiers prevent a naive cascade delete; decide approved anonymization
  or retention rules before migrations. Confirm how restored backups reapply completed
  deletions and how failed/partial requests recover. No deletion endpoint is added now.

## Business and integration launch gates

- [ ] Confirm a real vendor pilot agreement, inventory/hold/release terms, freshness
  evidence and operational ownership. Vendor search remains ongoing.
- [ ] Approve real pricing, fees, taxes and margin policy using verified sources.
- [ ] Select/approve payment, email OTP, notification and AI integrations; implement and
  verify provider-specific authentication, signatures, retries, reconciliation and
  sandbox failure scenarios before separately authorizing live traffic or spending.
- [ ] Resolve the PRD failure guarantee, refund/voucher scope, confirmed-booking failure
  handling, support process and customer terms. Current deferred remedies and terminal
  confirmed-booking behavior are not sufficient to promise the PRD guarantee.
- [ ] Approve notification content/channel and consent behavior. Disabled adapters and
  synthetic receipts are not evidence of customer delivery or real payments.

## Next roadmap step: Step 12 — Pilot (blocked; not started)

After closing the launch gates and explicit authorization, run 10 real paid bookings
with ops handling. Record cost and failures per booking and the PRD's success/ops time/
margin/refund/repeat metrics using verified provider/vendor records. Define stop and
incident escalation criteria before taking money. Do not invent prices or pretend
refund capabilities exist. No pilot, client app or WhatsApp automation is authorized
by Step 11; subsequent client work requires the roadmap's platform decision.

## Local verification evidence — 2026-10-24

- Full regression suite: 292 passed; four existing Starlette/HTTPX and Alembic
  deprecation warnings. No runtime behavior or existing package versions changed.
- `pip-audit --strict`: no known vulnerabilities in the installed locked environment.
- Recovery: all 23 public tables matched, including migration metadata; restored audit
  immutability and foreign-key rejection verified. Temporary restore DB/dump removed.
- Docker build/start/health passed. Load smoke: 80 requests, concurrency 8, measured
  p95 0.067 seconds and max 0.082 seconds. An initial invocation before container
  startup completed failed; rerunning after Compose reported healthy passed.
- Ruff lint/format and Alembic schema consistency passed.
- Redacted Gitleaks scans: zero findings in publishable working files and all available
  Git history. Intentional local `.env` excluded from file scanning, unchanged and
  untracked; this exclusion is not evidence about its contents. Scans are heuristic.
- CI changes are local and unpushed; remote GitHub Actions is unverified.

The approved local implementation/review work is complete. The roadmap's full
pre-launch acceptance criterion is not yet met: unchecked launch gates remain.
