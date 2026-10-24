# Elsewhere — fixture-only web demo

Run `npm install`, then `npm run dev` from this directory. Open http://localhost:3000.

Run `npm test` (Node 22.18+ with native TypeScript support) and `npm run build` to verify changes.

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
payment integrations or deployment configuration. Only the colour-theme preference is saved locally.

All experience fixtures live in `src/lib/fixtures.ts`. Questions live in the typed
`src/lib/questions.ts` configuration. Sample times are fixed on 24 October 2026
and displayed in Asia/Kolkata. Sample totals are for two. Options now exclude unavailable
and over-budget samples; other answers (group size, timing and requirements) remain unverified. One option is unavailable and one has unknown travel time.
No real inventory, booking, supplier, payment, or cancellation policy is represented.

The interface uses system fonts and locally hosted photographs, with no UI kit.
See `IMAGE_CREDITS.md` for source links and credits. Photo credits are also available
in the app footer. Activity photos are representative, not evidence of an event or venue.

## Chat-only planning

All planning prompts now use the chat composer, including the existing
`/questions/[field]` links used to edit a brief. Three optional starter ideas
(tonight, a relaxed date, and a forgotten anniversary) add editable text to the
composer without sending it. Follow-up questions use free text, with no
multiple-choice answers. Dates, times, areas and other preferences
are preserved in the user's own words; budget validation still uses integer paise.
Enter sends, Shift+Enter adds a line, and IME composition does not submit.

Replies remain explicitly labelled as a preview with AI offline. A conservative
question check keeps obvious follow-up questions from overwriting the current
preference and repeats the active prompt. This is not semantic understanding and
cannot answer general questions. Live OpenAI replies require an approved spending
limit, server-side provider configuration, and production authentication/backend
setup; the current FastAPI backend intentionally allows local/test use only.
No OpenAI requests or paid services are enabled by these frontend changes.

The Siri-inspired treatment uses a static luminous orb, soft surfaces and a
single composer. Typing and sending stay immediate, with no decorative motion
on keyboard input and no simulated microphone/listening state. Check the visual
balance, touch keyboard and narrow-screen layout on a real device before release.

Conversation state and drafts stay in memory across navigation and reset on
refresh. An explicit budget in the opening idea is captured and not asked again.

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

## Theme and budget

The header theme toggle follows the device preference initially and remembers an
explicit choice across navigation and refresh when storage is available. When
storage is blocked, the toggle still works for the current page session. Dark colours cover Chat, Discover and planning screens.

Budget matching uses integer paise, includes exact-price matches, and guards
detail/checkout actions as well as the list. ₹500 returns no available sample
because existing synthetic totals start at ₹1,800. The UI does not fabricate
cheaper prices, scale a two-person quote, or claim to generate live packages.
Real budget-based packages still need backend integration and verified inventory pricing.

## Curved Discover collection

The supplied TiltedGridHero is adapted in `src/components/ui/tilted-grid-hero.tsx`,
with a colocated CSS Module. This keeps reusable visual components separate from
the Discover screen and preserves the reference import structure. TypeScript is
already configured; Tailwind/shadcn setup is unnecessary for this CSS Modules
adaptation. No additional packages or external image hosts are introduced.

The decorative photo band uses the existing credited local images, curved into
16 facets per tile. Transform-based motion advances one tile every four seconds,
pauses off-screen and has a keyboard-accessible pause/resume control. Reduced
motion uses explicit static tile positions so the app-wide animation override
does not collapse the images onto each other. The accessible event links remain
in the responsive collage below, with the same search, filters and disclosures.

Check the curved image alignment, pause/resume, reduced-motion still layout and
light/dark mobile layouts in a browser before release. Browser automation was
unavailable during implementation.
