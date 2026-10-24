export type TripProfile = { tripAbroad: string; policyExpiry: string };
export type PartnerOffer = {
  id: string; category: "travel-cover"; partner: string; plan: string;
  coverPaise: number; premiumPaise: number; inclusions: string[]; exclusions: string[];
  waitingPeriods: string; validity: string; cancellation: string; expiresAt: string;
};
export type BookingNotice = { id: string; type: "booking"; title: string; message: string; read: boolean };
export type OfferNotice = { id: string; type: "offer"; offer: PartnerOffer; trigger: TripProfile; read: boolean };
export type InboxItem = BookingNotice | OfferNotice;
export type OfferEvent = "offer_viewed" | "offer_dismissed" | "offer_purchase_started";

// Fictional demonstration data. No partner, insurance contract, payment or booking exists.
export const sampleOffer: PartnerOffer = {
  id: "sample-travel-cover", category: "travel-cover", partner: "Sample Insurer",
  plan: "Sample Travel Cover", coverPaise: 10_000_000, premiumPaise: 49_900,
  inclusions: ["Partner benefit details not supplied in this demo."],
  exclusions: ["Partner exclusion details not supplied in this demo."],
  waitingPeriods: "Not supplied by a partner in this demo.",
  validity: "Policy validity not supplied by a partner in this demo.",
  cancellation: "Free-look and cancellation terms not supplied by a partner in this demo.",
  expiresAt: "2027-01-31T18:29:59Z",
};
// Public artwork references, identical for everyone; not verified inventory or partners.
export const showcaseOffers = [
  { id: "boat", brand: "boAt", image: "/images/offers/boat.webp", title: "Grand Festive Sale", source: "boAt official website", sourceUrl: "https://www.boat-lifestyle.com/", note: "Online promotion artwork dated 21–25 October. Current pricing, terms and delivery eligibility must be checked with the brand." },
  { id: "federal-bank", brand: "Federal Bank", image: "/images/offers/federal-bank.webp", title: "Weekend dining offers", source: "Weekends With Federal", sourceUrl: "https://www.federal.bank.in/weekends-with-federal", note: "Adapted from the bank’s published dining offer. Current validity and participating Kochi restaurants are unverified. Representative photograph." },
  { id: "honda", brand: "Honda", image: "/images/offers/honda.webp", title: "Aryabhangy Honda · Kochi area", source: "Aryabhangy Honda offers page", sourceUrl: "https://aryabhangymotors.com/offers.php", note: "Undated dealer artwork. Displayed prices and availability are not verified as current; check with the dealer." },
] as const;
export const bookingFixtures: BookingNotice[] = [
  { id: "sample-booking-1", type: "booking", title: "Sample booking request received", message: "Fixture update: your sample experience is awaiting vendor review. No real booking exists.", read: false },
  { id: "sample-booking-2", type: "booking", title: "Sample booking review update", message: "Fixture update: the sample request is still awaiting vendor review. No vendor has been contacted.", read: false },
];
export const sampleApplicants = [
  { id: "sample-a", name: "Sample Applicant A", email: "sample-a@example.invalid" },
  { id: "sample-b", name: "Sample Applicant B", email: "sample-b@example.invalid" },
] as const;

export function validExpiry(value: string): boolean {
  const date = value.trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return false;
  const time = Date.parse(`${date}T00:00:00Z`);
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === date;
}
export function matchesOfferInput(input: TripProfile): boolean {
  // Explicit demo rule: both fields supplied. No expiry-window or insurance-need inference.
  return input.tripAbroad === "Trip abroad" && validExpiry(input.policyExpiry);
}
export function offerKey(input: TripProfile): string {
  return JSON.stringify([sampleOffer.id, input.tripAbroad, input.policyExpiry]);
}
export function offerIsCurrent(offer: PartnerOffer): boolean {
  return Date.now() < Date.parse(offer.expiresAt);
}
export function logOfferEvent(event: OfferEvent) {
  console.info(event); // Event name only: no identifiers, trigger inputs or form contents.
}
