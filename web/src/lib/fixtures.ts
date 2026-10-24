export type DemoOption = {
  id: string;
  title: string;
  category: string;
  area: string;
  description: string;
  pricePaise: number;
  inclusions: string[];
  durationMinutes: number;
  travelMinutes: number | null;
  availability: "AVAILABLE" | "UNAVAILABLE";
  cancellationTerms: string;
  startsAt: string;
  art: "water" | "clay" | "table";
};

export const intents = [
  { id: "tonight", title: "Find a little adventure", subtitle: "Something to do now or tonight", icon: "↗", enabled: true },
  { id: "date", title: "Make time for two", subtitle: "A date worth putting your phone away for", icon: "♡", enabled: false },
  { id: "birthday", title: "Make their day", subtitle: "Birthdays, surprises & little celebrations", icon: "✳", enabled: false },
] as const;

export const options: DemoOption[] = [
  {
    id: "waterfront", title: "A slower evening by the water", category: "Walk + café", area: "Fort Kochi",
    description: "Take the scenic way into the evening. A gentle waterfront walk, a cosy café stop, and time to just be.",
    pricePaise: 180000, inclusions: ["Guided waterfront walk", "Two café drinks", "A shared snack plate"],
    durationMinutes: 120, travelMinutes: 25, availability: "AVAILABLE",
    cancellationTerms: "Demo terms: cancel at least 6 hours before the start for a full refund. Later cancellations are not refundable.",
    startsAt: "2026-10-24T12:00:00Z", art: "water",
  },
  {
    id: "clay", title: "A little mess. A lovely memory.", category: "Hands-on workshop", area: "Panampilly Nagar",
    description: "Slow down and make something with your hands. A beginner-friendly clay session with room for imperfect little masterpieces.",
    pricePaise: 240000, inclusions: ["Introductory clay session for two", "Materials and tools", "One small air-dry piece each"],
    durationMinutes: 90, travelMinutes: null, availability: "AVAILABLE",
    cancellationTerms: "Demo terms: cancel at least 12 hours before the start for a full refund. Later cancellations are not refundable.",
    startsAt: "2026-10-24T13:00:00Z", art: "clay",
  },
  {
    id: "supper", title: "Good food, an unhurried table", category: "Dining experience", area: "Marine Drive",
    description: "A relaxed evening around a shared table, with a seasonal three-course menu and conversation that can take its time.",
    pricePaise: 320000, inclusions: ["Three-course meal for two", "Two non-alcoholic drinks", "Reserved table"],
    durationMinutes: 120, travelMinutes: 15, availability: "UNAVAILABLE",
    cancellationTerms: "Demo terms: cancel at least 24 hours before the start for a full refund. Later cancellations are not refundable.",
    startsAt: "2026-10-24T14:00:00Z", art: "table",
  },
];

export const timeline = [
  { title: "Request received", description: "Your demo request has been recorded in this browser session.", current: false },
  { title: "Awaiting vendor confirmation", description: "No vendor has been contacted. This is a simulated pending state.", current: true },
  { title: "Next update", description: "In the real service, the team would contact you with the vendor’s response.", current: false },
];

export function formatMoney(paise: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paise / 100);
}

export function formatTime(iso: string) {
  return new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }).format(new Date(iso));
}
