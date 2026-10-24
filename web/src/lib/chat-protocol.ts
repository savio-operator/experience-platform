import type { Answers } from "./questions";
import type { ChatMessage } from "./chat-history";

export type ChatReply = { reply: string; preferences: Answers };
export const MAX_BODY_BYTES = 32_768;
export const MAX_CONTEXT_BYTES = 16_000;
const preferenceKeys = ["when", "where", "who", "occasion", "budget", "kind", "constraints", "transport"] as const;
const encoder = new TextEncoder();

function record(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
export function parsePreferences(value: unknown): Answers | null {
  if (!record(value) || Object.keys(value).some(key => !preferenceKeys.includes(key as keyof Answers))) return null;
  const answers: Answers = {};
  for (const key of preferenceKeys) {
    const field = value[key];
    if (field === undefined || field === null) continue;
    if (key === "budget") {
      if (typeof field !== "number" || !Number.isSafeInteger(field) || field < 100 || field > 100_000_000) return null;
      answers.budget = field;
    } else {
      if (typeof field !== "string" || !field.trim() || field.length > 1000) return null;
      answers[key] = field.trim();
    }
  }
  return answers;
}
export function parseChatReply(value: unknown): ChatReply | null {
  if (!record(value) || typeof value.reply !== "string" || !value.reply.trim() || value.reply.length > 12000) return null;
  const preferences = parsePreferences(value.preferences);
  return preferences ? { reply: value.reply.trim(), preferences } : null;
}
export function recentContext(messages: ChatMessage[]): Pick<ChatMessage, "role" | "text">[] {
  const result: Pick<ChatMessage, "role" | "text">[] = [];
  let bytes = 0;
  for (const message of [...messages].reverse().slice(0, 20)) {
    const size = encoder.encode(message.text).length;
    if (bytes + size > MAX_CONTEXT_BYTES) break;
    bytes += size;
    result.unshift({ role: message.role, text: message.text });
  }
  return result;
}
export function parseChatRequest(value: unknown): { messages: Pick<ChatMessage, "role" | "text">[]; answers: Answers } | null {
  if (!record(value) || !Array.isArray(value.messages) || !value.messages.length || value.messages.length > 20) return null;
  const answers = parsePreferences(value.answers);
  if (!answers) return null;
  let bytes = 0;
  const messages: Pick<ChatMessage, "role" | "text">[] = [];
  for (const message of value.messages) {
    if (!record(message) || (message.role !== "user" && message.role !== "assistant") || typeof message.text !== "string" || !message.text.trim() || message.text.length > (message.role === "user" ? 4000 : 12000)) return null;
    bytes += encoder.encode(message.text).length;
    messages.push({ role: message.role, text: message.text });
  }
  if (bytes > MAX_CONTEXT_BYTES || messages.at(-1)?.role !== "user") return null;
  return { messages, answers };
}

export const replySchema = {
  type: "object", additionalProperties: false, required: ["reply", "preferences"],
  properties: {
    reply: { type: "string" },
    preferences: {
      type: "object", additionalProperties: false, required: [...preferenceKeys],
      properties: Object.fromEntries(preferenceKeys.map(key => [key, key === "budget" ? { type: ["integer", "null"], description: "Explicit total budget for the whole group in integer paise; rupees multiplied by 100. Null if unknown or ambiguous." } : { type: ["string", "null"] }])),
    },
  },
};
