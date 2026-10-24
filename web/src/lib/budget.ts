// Demo-only budget matching. Real quotes must come from the backend.
export function parseBudget(text: string, allowBareAmount = false): number | null {
  if (/\b(?:per\s+(?:person|head)|each)\b/i.test(text)) return null;
  if (/\d\s*(?:-|–|to|and)\s*(?:₹|Rs\.?|INR)?\s*\d/i.test(text)) return null;
  const amount = "[+-]?\\d[\\d,.]*(?:\\s*[kK])?";
  const matches = [...text.matchAll(new RegExp(`(?<![\\w.,+-])(?:₹|\\bINR\\b|\\bRs\\.?)\\s*(${amount})(?![\\w.,+-])|(?<![\\w.,+-])(${amount})\\s*(?:rupees?\\b|rs\\b|₹)`, "gi"))];
  const raw = matches.length === 1 ? matches[0][1] ?? matches[0][2]
    : matches.length === 0 && allowBareAmount ? text.trim() : "";
  if (!/^(?:\d+|\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})$/.test(raw)) return null;
  const rupees = Number(raw.replaceAll(",", ""));
  return Number.isSafeInteger(rupees) && rupees >= 1 && rupees <= 1_000_000 ? rupees * 100 : null;
}

export function fitsBudget(option: { pricePaise: number; availability: string }, budget?: number): boolean {
  return Number.isSafeInteger(budget) && budget! > 0 && budget! <= 100_000_000
    && Number.isSafeInteger(option.pricePaise) && option.pricePaise >= 0
    && option.availability === "AVAILABLE" && option.pricePaise <= budget!;
}
