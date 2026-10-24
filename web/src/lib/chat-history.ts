import type { Answers } from "./questions";

export type ChatMessage = { role: "user" | "assistant"; text: string; source?: "demo" | "openai" };
export type ChatState = { draft: string; idea: string; messages: ChatMessage[]; questionIndex: number };
export type Conversation = {
  version: 1; id: string; createdAt: string; updatedAt: string;
  chat: ChatState; answers: Answers; inspirationId: string | null;
  selectedId: string | null; requested: boolean;
};
export const HISTORY_PREFIX = "elsewhere.chat.v1:";
export const ACTIVE_CHAT_KEY = "elsewhere.active-chat.v1";
type StorageReader = Pick<Storage, "length" | "key" | "getItem">;

export function createConversation(id: string, now = new Date().toISOString()): Conversation {
  return { version: 1, id, createdAt: now, updatedAt: now, chat: { draft: "", idea: "", messages: [], questionIndex: -1 }, answers: {}, inspirationId: null, selectedId: null, requested: false };
}

export function conversationTitle(conversation: Conversation): string {
  const text = conversation.chat.idea || conversation.chat.messages.find(message => message.role === "user")?.text || conversation.chat.draft;
  return text.trim().replace(/\s+/g, " ").slice(0, 72) || "New conversation";
}

export function hasContent(conversation: Conversation): boolean {
  return Boolean(conversation.chat.draft.trim() || conversation.chat.messages.length || conversation.inspirationId || Object.keys(conversation.answers).length);
}

export function parseConversation(raw: string): Conversation | null {
  try {
    const value = JSON.parse(raw);
    if (!value || value.version !== 1 || typeof value.id !== "string" || !/^[\w-]{1,80}$/.test(value.id)) return null;
    if (![value.createdAt, value.updatedAt].every(date => typeof date === "string" && Number.isFinite(Date.parse(date)))) return null;
    const chat = value.chat;
    if (!chat || typeof chat.draft !== "string" || chat.draft.length > 8000 || typeof chat.idea !== "string" || chat.idea.length > 8000 || !Number.isInteger(chat.questionIndex) || chat.questionIndex < -1 || chat.questionIndex > 8 || !Array.isArray(chat.messages)) return null;
    if (!chat.messages.every((message: ChatMessage) => message && ["user", "assistant"].includes(message.role) && typeof message.text === "string" && message.text.length <= 24000 && (message.source === undefined || ["demo", "openai"].includes(message.source)))) return null;
    if (!value.answers || typeof value.answers !== "object" || Array.isArray(value.answers)) return null;
    const answers: Answers = {};
    for (const key of ["when", "where", "who", "occasion", "kind", "constraints", "transport"] as const) {
      if (value.answers[key] !== undefined) {
        if (typeof value.answers[key] !== "string" || value.answers[key].length > 8000) return null;
        answers[key] = value.answers[key];
      }
    }
    if (value.answers.budget !== undefined) {
      if (!Number.isSafeInteger(value.answers.budget) || value.answers.budget < 0 || value.answers.budget > 100_000_000) return null;
      answers.budget = value.answers.budget;
    }
    if (![value.inspirationId, value.selectedId].every(id => id === null || (typeof id === "string" && /^[\w-]{1,80}$/.test(id)))) return null;
    return { version: 1, id: value.id, createdAt: value.createdAt, updatedAt: value.updatedAt, chat: { draft: chat.draft, idea: chat.idea, questionIndex: chat.questionIndex, messages: chat.messages.map((message: ChatMessage) => ({ role: message.role, text: message.text, ...(message.source ? { source: message.source } : {}) })) }, answers, inspirationId: value.inspirationId, selectedId: value.selectedId, requested: value.requested === true };
  } catch { return null; }
}

export function readConversations(storage: StorageReader): { conversations: Conversation[]; unreadable: number } {
  const conversations: Conversation[] = [];
  let unreadable = 0;
  for (let index = 0; index < storage.length; index++) {
    const key = storage.key(index);
    if (!key?.startsWith(HISTORY_PREFIX)) continue;
    const conversation = parseConversation(storage.getItem(key) || "");
    if (conversation && key === HISTORY_PREFIX + conversation.id) conversations.push(conversation);
    else unreadable++;
  }
  conversations.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  return { conversations, unreadable };
}
