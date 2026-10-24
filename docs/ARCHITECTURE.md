# ARCHITECTURE.md

## Principles
- Modular monolith: ONE deployable backend, clearly separated modules, one PostgreSQL database. No microservices, no Kubernetes, no Kafka in the MVP.
- Stateless API servers: no user state in memory. State lives in the database. (The database itself is stateful by definition, and that is fine.)
- Three authorities: AI layer proposes -> Rules layer validates -> Transaction layer executes. The AI never writes bookings or touches payments directly.
- Boring, managed, well-documented tech. Prefer managed services over self-hosting.

## Default stack (confirm in planning)
- Language/API: Python + FastAPI (alternative: TypeScript). 
- Database: PostgreSQL (managed). Migrations in version control.
- Jobs: simple job queue in Postgres or a managed queue. Redis only when needed (rate limit store, cache).
- Payments: an Indian payment gateway (e.g. Razorpay or Cashfree; verify fees/terms). Never handle raw card data.
- Messaging: WhatsApp Business API provider for customer chat later; SMS/email as fallback.
- AI: provider-agnostic interface (OpenAI first because of credits). Cheap model for intent parsing, stronger model for planning. Swappable.
- Infra: Docker for local and deploy, GitHub Actions CI/CD, separate dev/staging/prod, managed secrets, HTTPS everywhere, managed load balancer from the host. Object storage (S3-compatible) only when files exist.
- Observability: structured logs with correlation IDs, error tracking (e.g. Sentry), uptime checks.

## Folder structure
/backend
  /app
    /api          routers, request/response schemas, auth dependencies
    /modules
      /identity       users, roles, sessions
      /customers      profile, consent, saved preferences
      /vendors        vendors, contacts, terms, reliability
      /catalogue      services (static info)
      /inventory      slots, holds, release windows, availability state
      /pricing        quotes, fees, commissions, margin check
      /intents        parsed requests, conversation state
      /planning       candidate plans, constraint validation, alternatives
      /bookings       booking + component state machines, orchestration
      /payments       payment attempts, refunds, vouchers, reconciliation
      /notifications  templates, delivery, reminders
      /ops            admin tools, case queue
      /audit          append-only audit log
    /ai           provider interface, prompts, JSON schemas, tool definitions
    /core         config, db, security, rate limiting, logging, errors
    /jobs         background workers, scheduled tasks
  /migrations
  /tests
/docs             PRD, ARCHITECTURE, AIRULES, PLAN, decisions log
/infra            Dockerfile, compose, CI workflows
/ios              (later) SwiftUI client

## Data rules
- Money: integer paise, never floats. Timestamps in UTC, display in Asia/Kolkata.
- Every external-facing ID is a UUID. Idempotency keys on booking and payment actions.
- Inventory states: UNKNOWN, AVAILABLE_UNVERIFIED, AVAILABLE_VERIFIED, HELD, BOOKING_PENDING, CONFIRMED, UNAVAILABLE, EXPIRED.
- Booking states (separate from payment states): DRAFT, AWAITING_CUSTOMER, PAYMENT_PENDING, VENDOR_CONFIRMATION_PENDING, PARTIALLY_CONFIRMED, CONFIRMED, FULFILLED, FAILED, REFUND_PENDING, REFUNDED, MANUAL_INTERVENTION. Every transition is logged.
- Core tables: users, roles, customers, consents, vendors, services, inventory_slots, holds, quotes, intents, plans, plan_items, bookings, booking_components, payments, refunds, vouchers, notifications, cases, audit_events, jobs.
- Audit log is append-only. No sensitive conversation content stored by default.
- Raw AI inputs/outputs are untrusted. All model outputs validated against strict schemas.

## Security and reliability
- Rate limiting on every public endpoint, stricter on auth, search and AI endpoints.
- RBAC plus per-record ownership checks. Never trust IDs or roles from the client.
- Webhook signature verification and duplicate-delivery handling. Payment status confirmed server-side only.
- Secrets only on the server (environment or managed secret store). Never in the repo or the app.
- Prompt-injection defence: vendor text and user text are data, not instructions. AI has narrowly scoped tools only.
- Backups with a tested restore. Dependency scanning in CI. DPDP: consent capture, minimisation, deletion flow.
