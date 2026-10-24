// Preview guard only, not AI classification. Questions must not become preferences.
export function isFollowUpQuestion(text: string): boolean {
  return /\?\s*$/.test(text) || /^(?:what|why|how|who|where|when|can you|could you|tell me|explain|do you|are you|is there)\b/i.test(text.trim());
}
