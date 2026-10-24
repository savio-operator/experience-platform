# PLAN.md: Roadmap. ONE STEP AT A TIME.

Rule: implement and verify one step at a time. After completion, report actual results and automatically inspect and prepare a concise plan for the next numbered step. Present that plan and wait for authorization before implementation. Do not prebuild later steps. If the roadmap is complete, report that instead. All gates below remain in force.

GATE: Do not start Step 3 until at least one real vendor has agreed to a pilot (even verbally). Steps 0-2 are safe either way.

## Step 0: Foundation
Repo, folders per ARCHITECTURE.md, Docker, .env handling, CI (lint, tests), config module, health endpoint, structured logging.
Done when: app runs in Docker, CI is green, no secrets in repo.

## Step 1: Database and identity
Postgres schema v1 (users, roles, customers, consents), migrations, signup/login (phone or email OTP), sessions, RBAC, rate limiting on auth.
Done when: tests pass for auth, permissions and rate limits.

## Step 2: Vendors and catalogue (ops-managed)
Vendors, services, ops-only admin endpoints to add and edit them, audit log.
Done when: ops can create a vendor and a service, customers cannot.

## Step 3: Inventory and holds
Slots, holds with release windows, availability states and freshness, race-condition safe holds.
Done when: concurrent hold tests prove no double-booking.

## Step 4: Intent parsing (AI)
Provider-agnostic AI interface, structured intent schema, missing-field detection, strict output validation, prompt-injection tests, cost logging.
Done when: sample requests become valid structured intents; bad output is rejected.

## Step 5: Constraints and pricing
Hard vs soft constraints, price components, fees, taxes, budget check, separate margin check.
Done when: plans violating hard constraints never pass.

## Step 6: Options generation
Retrieve verified services, build up to 3 distinct plans, rank, label availability status honestly.
Done when: a request returns options built only from verified inventory.

## Step 7: Booking state machine
Booking and component states, ops confirmation flow, expiry jobs, audit trail.
Done when: "confirmed" is unreachable without vendor confirmation.

## Step 8: Payments, refunds, guarantee
Gateway test mode, webhooks with signature checks, idempotency, refunds, voucher guarantee, reconciliation job.
Done when: duplicate webhooks and payment-succeeds-booking-fails cases are handled by tests.

## Step 9: Notifications
Confirmation, reminders, change and failure notices via WhatsApp/SMS/email provider, with delivery tracking.
Done when: messages only send after verified state.

## Step 10: Ops dashboard and cases
In-progress bookings, pending confirmations, failures, refunds, escalation queue.
Done when: ops can resolve a failed booking end to end.

## Step 11: Hardening
Security checklist, error tracking, alerts, backups and restore test, load smoke test, staging environment, DPDP consent and deletion flows.
Done when: pre-launch checklist is complete.

## Step 12: Pilot
Run 10 real paid bookings with ops handling. Log cost and failures per booking.
Then, and only then: client app (platform decision first), WhatsApp bot, and further automation.
