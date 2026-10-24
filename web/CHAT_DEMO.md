# Current chat demo

These notes supersede the older in-memory chat and starter-button notes in
README.md. AIRULES.md and PLAN.md are unchanged.

## History and photos

Chat at `/` has scrollable, searchable history. Phones use the **Chat history**
button. Create, reopen, download text and delete conversations. Drafts, messages,
preferences, discovery inspiration and simulated request state persist separately
per conversation in this browser's localStorage. Refresh reopens the active chat.
There are no accounts or cloud backups: clearing site data removes history, and
anyone sharing the browser can read it. Storage failures show a warning; corrupt
entries are left untouched. There is no automatic pruning/deletion. Tabs load
history on opening/reload; editing the same chat in two tabs is last-write-wins.

Starter cards and multiple-choice controls are removed from Chat. Discover keeps
its photo reel, filters and event details. Remaining chat orbs use the credited
Fort Kochi photograph; assets are local. See IMAGE_CREDITS.md. Activities remain
synthetic examples, not verified events. Planning preferences still lead to the
sample brief/options/detail/checkout/request flow.

## Paid AI is OFF

The owner requested **Keep paid AI disabled for now**. `PAID_AI_APPROVED` is false.
No key or database is needed for history or demo features. `GET /api/chat` returns
`available:false`. POST fails before any database/provider call, even if env vars
are present. Scripted replies say **Demo guide** and cannot answer general questions.

The inactive Vercel endpoint is prepared for the OpenAI Responses API. It uses a
server-only key, bounded recent context, structured replies and validated planning
preferences. No booking, payment, browsing, vendor or inventory tools exist.
Model output renders as text, not HTML. No analytics/client AI SDK was added.

Only after explicit owner approval to enable paid AI:

1. Re-check official model behavior, availability and pricing; current policy
   expires on 24 November 2026 and then blocks requests.
2. Connect approved PostgreSQL and apply `scripts/chat-usage.sql` once. Never reset
   its lifetime budget row on deploy. Enabled preview/production deployments must
   share that row.
3. In Vercel's server settings add sensitive `OPENAI_API_KEY` and
   `CHAT_DATABASE_URL` (pooled PostgreSQL URL with validated TLS). Add
   `CHAT_AI_ENABLED=true` only after approval. No NEXT_PUBLIC_ secrets, repo values,
   screenshots of keys, terminal logging of secrets or disabled TLS validation.
4. Change the source approval flag with owner approval, run real database/provider
   integration checks, and redeploy. Those live checks have NOT been performed.
   No hosted database has been provisioned by this change.

## Prepared $10 lifetime guard

A PostgreSQL transaction locks one lifetime budget row before admission across
all Vercel instances. Every attempt irreversibly reserves $0.02 from $10 before
calling OpenAI. Reservations are conservative, NOT actual billed usage: at most
500 attempts, potentially stopping well before $10 is spent. Errors/timeouts keep
reservations because billing is uncertain. No reset/refill/refund or auto-retry.
If storage/policy fails, no paid call occurs.

Fixed model: `gpt-6-luna`, Standard processing, reasoning none, 2,048 output tokens,
no tools/media, maximum 40KB provider request JSON. Reviewed 24 October 2026:
input $0.10/M, cache writes $0.125/M, output $0.50/M tokens. With a conservative
16K framing-token allowance, bounded cost stays below the $0.02 reservation.
Re-review before enabling/changing limits. This guards this endpoint's API usage,
not other apps using the key, hosting/database charges, FX or taxes.

Global rate limit: 20 attempts/minute; signed browser session: 60 attempts/day.
Cookie: HttpOnly, SameSite=Strict, Secure in production. Origin/content-type/body
checks reject cross-site and malformed browser requests. This public demo is not
user authentication: visitors can rotate sessions and consume the allowance, but
cannot bypass the global budget row. The ledger stores a pseudonymous session
hash and timestamp, never chat content or keys.

OpenAI receives the latest 20 messages within 16KB plus current preferences.
Full history stays local. `store:false` is not a promise of zero provider retention.

Sources:
- https://developers.openai.com/api/docs/models/gpt-6-luna
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/guides/conversation-state

## Validation

`npm test` covers saved-data validation/isolation, protocol boundaries, context
limits, budgets and the fixed disabled cost policy. `npm run build` checks Next.js
and TypeScript. Database concurrency and live provider integration are unverified.
Real-phone keyboard/touch behavior still needs verification.
