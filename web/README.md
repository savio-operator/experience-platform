# Elsewhere — fixture-only web demo

Run `npm install`, then `npm run dev` from this directory. Open http://localhost:3000.

The only verification command for this time-boxed demo is `npm run build`.

## Flow

`/` → `/questions/when` → `/questions/where` → `/questions/who` →
`/questions/occasion` → `/questions/budget` → `/questions/kind` →
`/questions/constraints` → `/questions/transport` → `/brief` → `/options` →
`/options/waterfront` (or `/options/clay`, `/options/supper`) → `/checkout` → `/booking`.

Use the **Preview state** control on each screen to simulate loading, empty, and
error states. Retry/restore returns to normal content without changing answers.

Answers live only in React memory. Navigation preserves them; a full refresh
resets them. Direct links without the necessary answers show an empty state.
There are no backend requests, credentials, environment variables, analytics,
payment integrations, persistence, or deployment configuration.

All experience fixtures live in `src/lib/fixtures.ts`. Questions live in the typed
`src/lib/questions.ts` configuration. Sample times are fixed on 24 October 2026
and displayed in Asia/Kolkata. Sample totals are for two and are not matched to
the user's answers. One option is unavailable and one has unknown travel time.
No real inventory, booking, supplier, payment, or cancellation policy is represented.

The visual scenes use CSS shapes, system fonts, and no external assets or UI kit.
