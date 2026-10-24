# AIRULES.md: Rules for the AI coding assistant

## Working rules

-   Inspect relevant project rules, requirements and repository state before
    each task; avoid rereading unchanged documents. Work on ONE roadmap step
    at a time. Plan the next step automatically after completion, but do not
    implement it without authorization.
-   For an authorized implementation step, briefly state its objective and
    implement related changes together. Make routine decisions autonomously
    within the approved architecture; do not seek repeated plan approvals.
-   Ask only about material architecture, product, security, cost or data
    integrity decisions, genuine blockers, or destructive/production actions.
-   Reuse existing code and dependencies. Run focused checks when useful, then
    required final checks; fix failures and rerun affected checks. Do not repeat
    successful checks without a reason. Commit completed work locally when
    appropriate. Report actual results, acceptance criteria and limitations.
    Then inspect PLAN.md and relevant documentation and prepare a concise plan
    for the actual next step: objective, essential changes, dependencies,
    security, verification and genuine blockers. Present it for approval and
    wait for implementation authorization. If the roadmap is complete, report
    completion instead of inventing a step.
-   Optimize local verification: run affected tests during development and
    affected/integration tests before committing. Run the full suite at major
    milestones or when shared infrastructure, authentication, authorization,
    transactions or other critical components change. Reuse valid passing
    results; rerun only when inputs/dependencies change or failures require it.
    Keep CI quality gates intact. Run Docker, migrations and secret scans when
    relevant files change or at required release checkpoints. Report new results,
    regressions and outstanding failures; never claim unexecuted checks passed.
-   Never use Render credentials or perform Render account operations without
    explicit authorization for the specific operation. No unapproved cloud
    resources, costs, production changes or destructive Git operations.
-   Make small, focused changes. Each step ends with relevant
    tests/checks passing and a short summary of what changed, followed by
    the next-step plan. Do not move forward while required checks are failing.
-   Never add features, libraries or services not in the plan without
    asking.
-   If a requirement is risky, costly or unclear, say so instead of
    guessing.
-   Never print, log or commit secrets. Do not invent prices,
    availability, API behaviour or legal facts.
-   Inspect the existing repository and preserve its working framework,
    package manager, folder structure and deployment assumptions. Do not
    migrate or replace the stack without approval.
-   Build a responsive web experience suitable for mobile and desktop.
    Treat the website as the initial product; do not implement native
    iOS or Android clients unless the plan explicitly calls for them.
-   Vercel is a deployment platform, not automatically the host for
    every backend dependency. Confirm where the backend, database,
    background jobs and external integrations actually run before
    changing deployment configuration.

## Secrets and environment configuration (critical)

-   API keys, payment secrets, database credentials and supplier
    credentials must remain server-side, in local environment variables
    or an appropriate managed secret store. Never expose them in browser
    code, client bundles, source control or logs.
-   Treat every variable exposed through a client-side/public prefix
    (for example, `NEXT_PUBLIC_` in Next.js) as public. Never put
    secrets in such variables.
-   Provide or maintain a `.env.example` containing names and safe
    placeholder values only. Ensure real `.env` files are ignored by
    Git.
-   Validate required environment variables at server startup or
    deployment where practical. Fail safely with a clear operational
    error; do not reveal secret values.
-   Use separate environment configuration for local development,
    preview/staging and production. Never connect preview deployments to
    production data by accident.
-   Do not commit tokens, credentials, private keys, payment data or
    production data.

## Web client rules

-   Follow the framework and routing conventions already present in the
    repository. If the project is not yet established, propose a
    suitable Vercel-compatible web stack and wait for approval before
    introducing it.
-   Keep UI components focused on presentation. Put reusable business
    logic in appropriate modules/hooks/services, and keep server-only
    logic on the server.
-   Use a shared, typed API client for backend calls where appropriate.
    Centralise base URL configuration, authentication handling,
    timeouts, response validation and error mapping.
-   Never call OpenAI or other secret-bearing vendor APIs directly from
    browser code. Route those requests through a protected server-side
    endpoint or the existing backend.
-   Do not trust client-submitted prices, discounts, availability,
    supplier acceptance, payment status or booking status. The backend
    is the source of truth.
-   Every interactive screen must handle loading, empty, error and retry
    states. Explain pending, unavailable and failed booking states
    clearly; never display a pending booking as confirmed.
-   Build accessible interfaces: semantic HTML, keyboard navigation,
    visible focus, appropriate labels and contrast. Support narrow
    mobile screens as well as desktop layouts.
-   Use reusable components and consistent design tokens. Avoid
    unnecessary dependencies and premature abstractions.
-   Do not store sensitive tokens in localStorage or sessionStorage by
    default. Prefer secure, HttpOnly, Secure, SameSite cookies when
    compatible with the approved authentication design. Follow the
    existing auth architecture and document any trade-offs.
-   Protect authenticated pages and server endpoints on the server, not
    only by hiding UI elements. Verify ownership and permissions for
    every resource/action.

## Vercel and deployment rules

-   Keep the application compatible with the deployment model actually
    used by the repository. Do not assume that long-running processes,
    persistent local files or background workers can run inside a
    serverless function.
-   Use Vercel server-side functions only for work that fits their
    runtime and limits. Run durable background jobs, scheduled workflows
    or long-running tasks on an appropriate worker/platform if needed.
-   Do not store persistent user uploads or application data on the
    deployment filesystem. Use the approved database or object-storage
    service.
-   Configure environment variables separately for development, preview
    and production. Do not expose secrets to preview builds or untrusted
    branches.
-   Keep deployment configuration minimal and explain any changes to
    `vercel.json`, build commands, output directories, rewrites or
    environment variables before applying them.
-   Add a basic deployment smoke test for key routes and critical server
    endpoints. Verify that preview deployments work before production
    deployment when the workflow supports it.
-   Never claim a deployment succeeded unless the deployment result was
    actually checked.

## Backend rules

-   Follow ARCHITECTURE.md folder structure exactly. Keep business logic
    in the designated modules/services, not directly in route handlers.
-   Validate all inputs with schemas on the server. Use parameterised
    queries or the approved ORM. Represent money as integer paise; do
    not use floating-point arithmetic for financial calculations.
-   Every meaningful state change must pass through the relevant state
    machine and write an audit event.
-   All financial and booking actions must be idempotent. Handle
    retries, duplicate requests, provider timeouts and partial failures
    safely.
-   Treat AI output and external supplier responses as untrusted input.
    Validate schemas and business constraints before acting on them.
-   Booking, payment and supplier-confirmation statuses are separate.
    Only report a booking as confirmed after authoritative confirmation
    has been verified.
-   Test each critical module for success, failure and permission-denied
    paths. Include timeout/retry and duplicate-request tests for
    transactional flows.
-   Never allow the AI model to directly execute unrestricted database
    queries, change booking/payment states or access credentials.

## Security, privacy and reliability

-   Use HTTPS for deployed traffic. Validate authentication,
    authorisation, resource ownership and input on every protected
    server endpoint.
-   Apply appropriate rate limits to authentication, AI, search,
    booking, payment and supplier-facing endpoints. Rate limiting does
    not replace idempotency.
-   Verify payment and supplier webhooks using the provider's supported
    signature/authentication mechanism. Do not trust a browser redirect
    as proof of payment.
-   Log structured operational events with request/correlation IDs, but
    never log secrets, access tokens, payment-card data or unnecessary
    personal information.
-   Add error monitoring and health checks appropriate to the current
    project stage. Handle errors without leaking stack traces,
    credentials or internal details to users.
-   Use least-privilege credentials, dependency checks, backups and a
    documented recovery path appropriate to the stage of the project.
-   Keep user data minimised. Implement consent, access, retention and
    deletion behaviour according to the product requirements and
    applicable obligations.

## Testing and delivery

-   Before changing code, identify the exact PLAN.md step and its
    acceptance criteria.
-   Run the relevant formatter, linter, type checks, tests and
    production build available in the repository. Do not claim checks
    passed if they were not run.
-   Add or update tests for changed behaviour, especially validation,
    authentication, permissions, booking state transitions and failure
    paths.
-   Do not silence errors, weaken tests or bypass type checks just to
    make a build pass.
-   At the end of the approved step, report: files changed, behaviour
    implemented, checks run and their results, known limitations, and
    a concise implementation plan for the next actual roadmap step. Then stop
    and wait for authorization to implement it. Honor all roadmap gates.
