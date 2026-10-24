"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type Dispatch, type SetStateAction, type ReactNode } from "react";
import type { Answers, QuestionId } from "@/lib/questions";
import { ACTIVE_CHAT_KEY, HISTORY_PREFIX, createConversation, hasContent, readConversations, type ChatState, type Conversation } from "@/lib/chat-history";

export type { ChatState } from "@/lib/chat-history";
type Workspace = { activeId: string; conversations: Conversation[] };
type DemoState = {
  ready: boolean; storageWarning: string; conversations: Conversation[]; activeId: string;
  newChat: () => void; openChat: (id: string) => void; deleteChat: (id: string) => void;
  updateConversation: (id: string, update: (conversation: Conversation) => Conversation) => void;
  inspirationId: string | null; setInspirationId: Dispatch<SetStateAction<string | null>>;
  discovery: { category: string; area: string; query: string };
  setDiscovery: Dispatch<SetStateAction<{ category: string; area: string; query: string }>>;
  chat: ChatState; setChat: Dispatch<SetStateAction<ChatState>>;
  answers: Answers; answer: (id: QuestionId, value: string | number) => void;
  selectedId: string | null; select: (id: string) => void;
  requested: boolean; request: () => void; reset: () => void;
};
const DemoContext = createContext<DemoState | null>(null);
const placeholder = createConversation("initial", "2000-01-01T00:00:00.000Z");

export function DemoProvider({ children }: { children: ReactNode }) {
  const [workspace, setWorkspace] = useState<Workspace>({ activeId: placeholder.id, conversations: [placeholder] });
  const [ready, setReady] = useState(false);
  const [storageWarning, setStorageWarning] = useState("");
  const [discovery, setDiscovery] = useState({ category: "All", area: "All Kochi", query: "" });
  const persisted = useRef(new Map<string, Conversation>());
  const active = workspace.conversations.find(item => item.id === workspace.activeId) || placeholder;

  useEffect(() => {
    const fresh = createConversation(crypto.randomUUID());
    try {
      const { conversations, unreadable } = readConversations(localStorage);
      for (const item of conversations) persisted.current.set(item.id, item);
      let activeId: string | null = null;
      try { activeId = sessionStorage.getItem(ACTIVE_CHAT_KEY); } catch { /* History still works without tab storage. */ }
      setWorkspace({ activeId: conversations.find(item => item.id === activeId)?.id || conversations[0]?.id || fresh.id, conversations: conversations.length ? conversations : [fresh] });
      if (unreadable) setStorageWarning("Some saved chats couldn’t be read. Their data has been left untouched.");
    } catch { setWorkspace({ activeId: fresh.id, conversations: [fresh] }); setStorageWarning("Browser storage is unavailable. Chats will only last while this tab stays open."); }
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    try {
      for (const conversation of workspace.conversations) {
        if (!hasContent(conversation)) {
          if (persisted.current.has(conversation.id)) {
            localStorage.removeItem(HISTORY_PREFIX + conversation.id);
            persisted.current.delete(conversation.id);
          }
          continue;
        }
        if (persisted.current.get(conversation.id) === conversation) continue;
        localStorage.setItem(HISTORY_PREFIX + conversation.id, JSON.stringify(conversation));
        persisted.current.set(conversation.id, conversation);
      }
    } catch { setStorageWarning("Your latest changes couldn’t be saved in this browser. Keep this tab open or download the conversation before leaving."); }
    try { sessionStorage.setItem(ACTIVE_CHAT_KEY, workspace.activeId); } catch { /* Not required for saving chats. */ }
  }, [workspace, ready]);

  const updateConversation = useCallback((id: string, update: (conversation: Conversation) => Conversation) => {
    setWorkspace(previous => ({ ...previous, conversations: previous.conversations.map(item => item.id === id ? { ...update(item), id, updatedAt: new Date().toISOString() } : item) }));
  }, []);
  const updateActive = useCallback((update: (conversation: Conversation) => Conversation) => {
    setWorkspace(previous => ({ ...previous, conversations: previous.conversations.map(item => item.id === previous.activeId ? { ...update(item), updatedAt: new Date().toISOString() } : item) }));
  }, []);
  const setChat: Dispatch<SetStateAction<ChatState>> = useCallback(update => updateActive(item => ({ ...item, chat: typeof update === "function" ? update(item.chat) : update })), [updateActive]);
  const setInspirationId: Dispatch<SetStateAction<string | null>> = useCallback(update => updateActive(item => ({ ...item, inspirationId: typeof update === "function" ? update(item.inspirationId) : update })), [updateActive]);
  const newChat = useCallback(() => {
    const fresh = createConversation(crypto.randomUUID());
    setWorkspace(previous => {
      const blank = previous.conversations.find(item => !hasContent(item));
      return blank ? { ...previous, activeId: blank.id } : { activeId: fresh.id, conversations: [...previous.conversations, fresh] };
    });
  }, []);
  const openChat = useCallback((id: string) => setWorkspace(previous => previous.conversations.some(item => item.id === id) ? { ...previous, activeId: id } : previous), []);
  const deleteChat = useCallback((id: string) => {
    try { localStorage.removeItem(HISTORY_PREFIX + id); persisted.current.delete(id); }
    catch { setStorageWarning("This chat couldn’t be removed from browser storage. Please try again."); return; }
    const fresh = createConversation(crypto.randomUUID());
    setWorkspace(previous => {
      const remaining = previous.conversations.filter(item => item.id !== id);
      const conversations = remaining.length ? remaining : [fresh];
      return { conversations, activeId: previous.activeId === id ? [...conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))[0].id : previous.activeId };
    });
  }, []);

  return <DemoContext.Provider value={{
    ready, storageWarning, conversations: workspace.conversations, activeId: workspace.activeId,
    newChat, openChat, deleteChat, updateConversation, discovery, setDiscovery,
    inspirationId: active.inspirationId, setInspirationId, chat: active.chat, setChat, answers: active.answers,
    answer: (id, value) => updateActive(item => ({ ...item, answers: { ...item.answers, [id]: value }, selectedId: null, requested: false })),
    selectedId: active.selectedId, select: id => updateActive(item => ({ ...item, selectedId: id, requested: false })),
    requested: active.requested, request: () => updateActive(item => ({ ...item, requested: true })), reset: newChat,
  }}>{children}</DemoContext.Provider>;
}

export function useDemo() {
  const state = useContext(DemoContext);
  if (!state) throw new Error("Demo provider is missing");
  return state;
}
