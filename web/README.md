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

The interface uses system fonts and locally hosted photographs, with no UI kit.
See `IMAGE_CREDITS.md` for source links and credits. Photo credits are also available
in the app footer. Activity photos are representative, not evidence of an event or venue.

## Chat-first home

The home screen now has an editable chat composer and text suggestion buttons for
an evening, a date or a birthday. Date and birthday are visibly disabled as coming soon.
Clicking an enabled suggestion appends it to the draft and
focuses the textarea; it never sends automatically. Enter sends, Shift+Enter adds a
line, and IME composition does not submit. Empty drafts cannot be sent.

Replies are explicitly scripted demo prompts using the existing eight-question
configuration; no AI endpoint or provider is called. The conversation captures a
brief and leads into the existing review/options flow. Whole-rupee budget validation
is retained. The original idea is shown alongside the brief. Chat and unsent drafts
stay in provider memory across navigation/preview states and reset on refresh or
starting a new plan.

## Chat and Discover

The persistent mode switch opens Chat at `/` and Discover at `/discover`.
Discover has six synthetic event concepts, category and Kochi-area filters, search,
and details at `/discover/[id]`. The sample schedule is fixed on 24–25 October 2026,
formatted in Asia/Kolkata. No live event schedule, price, vendor, or availability is asserted.

“Bring this idea into Chat” adds a separate inspiration reference to the brief and
opens the existing conversation. It only fills the draft when both the draft and
conversation are empty; it never sends, overwrites answers, or resets an existing
conversation. The reference can be removed in Chat. Filters survive mode switches.
All of this state resets on a full refresh. Discovery offers loading, empty, and
error simulations plus an actual no-results state with a clear-filters action.

Photo assets are served from this app, so visitors do not contact the stock-photo
sites to load them. Source links only open when a visitor chooses a photo credit.

Validation: production build and TypeScript passed; local HTTP rendering checked.
Interactive browser automation was unavailable. Confirm keyboard, touch scrolling,
software-keyboard positioning and landscape safe areas on a real phone before release.
