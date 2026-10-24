// Preview guard only, not AI classification. Questions must not become preferences.
export function isFollowUpQuestion(text: string): boolean {
  return /\?\s*$/.test(text) || /^(?:what|why|how|who|where|when|can you|could you|tell me|explain|do you|are you|is there)\b/i.test(text.trim());
}

export function appendStarter(draft: string, starter: string, maxLength: number): string | null {
  const next = draft ? `${draft}${/\s$/.test(draft) ? "" : " "}${starter}` : starter;
  return next.length <= maxLength ? next : null;
}
