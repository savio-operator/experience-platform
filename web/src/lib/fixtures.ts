export const photos = {
  water: { src: "/images/kochi.jpg", alt: "Chinese fishing nets silhouetted against the sunset at Fort Kochi", position: "center 56%", credit: "Ankur Khanna / Unsplash", subject: "Fort Kochi", source: "https://unsplash.com/photos/black-sailing-boat-under-sunset-TbPRyHcxw7o" },
  clay: { src: "/images/pottery.jpg", alt: "Hands working clay with pottery tools", position: "center 55%", credit: "cottonbro studio / Pexels", subject: "Pottery", source: "https://www.pexels.com/photo/a-person-doing-pottery-6694323/" },
  table: { src: "/images/dining.jpg", alt: "A shared restaurant table with dishes and drinks", position: "center", credit: "ROMAN ODINTSOV / Pexels", subject: "Dining", source: "https://www.pexels.com/photo/dinner-at-restaurant-4871107/" },
  music: { src: "/images/music.jpg", alt: "An audience silhouetted beneath colourful concert lights", position: "center 43%", credit: "Daniel Marín / Pexels", subject: "Live music", source: "https://www.pexels.com/photo/lights-behind-crowd-on-concert-18384921/" },
  gallery: { src: "/images/gallery.jpg", alt: "Visitors looking at paintings in an art gallery", position: "center", credit: "Fran Augusto / Pexels", subject: "Art", source: "https://www.pexels.com/photo/visitors-observing-art-in-a-gallery-setting-33714764/" },
  yoga: { src: "/images/yoga.jpg", alt: "A woman practising yoga outdoors in Rishikesh, India", position: "center 45%", credit: "Rishikesh Yog Kendra / Pexels", subject: "Wellness", source: "https://www.pexels.com/photo/woman-practicing-yoga-outdoors-in-rishikesh-29534944/" },
} as const;
export type PhotoId = keyof typeof photos;

export type DiscoveryEvent = {
  id: string;
  title: string;
  category: "Outdoors" | "Workshops" | "Live music" | "Food" | "Art" | "Wellness";
  area: string;
  photo: PhotoId;
  startsAt: string;
  duration: string;
  description: string;
  note: string;
};

// Synthetic event concepts, not live listings. Dates are fixed demo dates in IST.
export const discoveryEvents: DiscoveryEvent[] = [
  { id: "sunset-walk", title: "Take the long way to sunset", category: "Outdoors", area: "Fort Kochi", photo: "water", startsAt: "2026-10-24T11:30:00Z", duration: "90 minutes", description: "A slow wander along the waterfront, a café stop, and a front-row seat to the evening. An idea for anyone who could use a little sea air.", note: "An outdoor walk concept. Route, accessibility, weather, and any café stop would need to be checked." },
  { id: "after-hours", title: "An evening with a live soundtrack", category: "Live music", area: "Kakkanad", photo: "music", startsAt: "2026-10-24T14:30:00Z", duration: "2 hours", description: "Find your people, find your spot, and let a good set take care of the evening. A live-music night to build a plan around.", note: "No artist or venue is booked. Age restrictions, line-up, entry fees, and tickets are not verified." },
  { id: "clay-club", title: "Less scrolling. More making.", category: "Workshops", area: "Panampilly Nagar", photo: "clay", startsAt: "2026-10-24T10:30:00Z", duration: "90 minutes", description: "Trade your screen for a little clay. A relaxed, beginner-friendly making session, with plenty of room for wonderfully imperfect results.", note: "A workshop concept. Instructor, materials, firing, collection, and access arrangements are not verified." },
  { id: "supper-club", title: "Good food. Even better company.", category: "Food", area: "Marine Drive", photo: "table", startsAt: "2026-10-24T14:00:00Z", duration: "2 hours", description: "Make room for a long conversation and a shared table. A dining idea for the kind of evening that doesn’t need much of an agenda.", note: "No restaurant is reserved. Menu, dietary requirements, prices, and table availability need verification." },
  { id: "art-afternoon", title: "A fresh perspective, frame by frame", category: "Art", area: "Fort Kochi", photo: "gallery", startsAt: "2026-10-25T05:30:00Z", duration: "90 minutes", description: "An unhurried gallery visit with time to look a little closer. A small dose of art, conversation, and inspiration for your weekend.", note: "An exhibition concept. No gallery programme, opening hours, curator, or entry fee has been verified." },
  { id: "slow-morning", title: "Start with a little breathing room", category: "Wellness", area: "Marine Drive", photo: "yoga", startsAt: "2026-10-25T01:00:00Z", duration: "60 minutes", description: "A gentle start, some fresh air, and a pause before the city picks up its pace. A movement and mindfulness idea for your morning.", note: "A wellness concept, not a scheduled class. Teacher, location permission, suitability, and facilities need verification." },
];

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
