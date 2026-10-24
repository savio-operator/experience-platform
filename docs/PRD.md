# PRD.md: Product Requirements (working name: Experience Platform)

## What the app is
A backend-first platform for last-minute and occasion experiences in Kochi (Ernakulam district). A customer says what they want ("date tonight, Rs 3,000, no alcohol"). AI proposes up to 3 options built ONLY from verified vendor inventory. Our ops team confirms with vendors, the customer pays, and we deliver and follow up.
The AI is the planning interface. The product is confirmed, fulfilled experiences.

## Who uses it
- Customer: Kochi professionals and college students, 18-40.
- Ops admin (us): confirms vendors, resolves failures, issues refunds. Vendors are handled by ops in the MVP, they get no software.
- AI assistant: proposes, never decides.

## MVP scope (Kochi only)
Three intents only:
1. Find something to do now or tonight
2. Plan a date
3. Plan a birthday or surprise
Core flow: request -> structured requirements -> options (from verified inventory) -> customer picks -> price check -> payment -> vendor confirmation -> reminders -> feedback.

## Product rules
- A recommendation is not a booking. A booking request is not a confirmation. Never say "confirmed" until the vendor has confirmed.
- Never show a service we cannot actually confirm.
- The AI must not invent prices, availability, bookings or confirmations.
- Budget check (customer) and margin check (business) are separate checks.
- Failure guarantee: if a confirmed booking fails, full refund plus a credit voucher. Voucher multiplier and expiry are configurable (idea: 3x, 7 days). Price this before launch and get legal review.

## What the app is NOT
- Not a trip or tour-package seller. No intercity, flights, trains or accommodation.
- Not inbound tourism. Not multi-city.
- Not vendor software or a self-serve supplier marketplace (ops manages vendors).
- Not a leftover-inventory seller. We only list slots we hold or have pre-agreed.
- Not a ticket reseller or secondary market.
- Not a data business in the MVP. No selling personal data, ever.
- Not an "everything platform". No subscriptions, social features, loyalty tiers, sponsored placements, or live supplier API integrations in the MVP.

## Success metrics (first 8 weeks)
10 paid bookings, then 50. Booking success rate, ops minutes per booking, contribution margin per booking (after payment fees and refunds), refund and failure rate, customer repeat rate.

## Open decisions (do not guess, ask)
Client platform (iOS only or also Android, as most Indian users are on Android), vendor hold and return terms, fee model (flat fee vs commission), budget, who builds and operates, payment provider.
