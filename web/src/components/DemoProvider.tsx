"use client";

import { createContext, useContext, useState, type Dispatch, type SetStateAction, type ReactNode } from "react";
import type { Answers, QuestionId } from "@/lib/questions";

export type ChatState = {
  draft: string;
  idea: string;
  messages: { role: "user" | "assistant"; text: string }[];
  questionIndex: number;
};
const emptyChat: ChatState = { draft: "", idea: "", messages: [], questionIndex: -1 };

type DemoState = {
  inspirationId: string | null;
  setInspirationId: Dispatch<SetStateAction<string | null>>;
  discovery: { category: string; area: string; query: string };
  setDiscovery: Dispatch<SetStateAction<{ category: string; area: string; query: string }>>;
  chat: ChatState;
  setChat: Dispatch<SetStateAction<ChatState>>;
  answers: Answers;
  answer: (id: QuestionId, value: string | number) => void;
  selectedId: string | null;
  select: (id: string) => void;
  requested: boolean;
  request: () => void;
  reset: () => void;
};
const DemoContext = createContext<DemoState | null>(null);

export function DemoProvider({ children }: { children: ReactNode }) {
  const [inspirationId, setInspirationId] = useState<string | null>(null);
  const [discovery, setDiscovery] = useState({ category: "All", area: "All Kochi", query: "" });
  const [chat, setChat] = useState<ChatState>(emptyChat);
  const [answers, setAnswers] = useState<Answers>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [requested, setRequested] = useState(false);
  return <DemoContext.Provider value={{
    inspirationId, setInspirationId, discovery, setDiscovery,
    chat, setChat,
    answers,
    answer: (id, value) => {
      setAnswers(previous => ({ ...previous, [id]: value }));
      setSelectedId(null); setRequested(false);
    },
    selectedId,
    select: id => { setSelectedId(id); setRequested(false); },
    requested,
    request: () => setRequested(true),
    reset: () => { setChat(emptyChat); setAnswers({}); setSelectedId(null); setRequested(false); setInspirationId(null); },
  }}>{children}</DemoContext.Provider>;
}

export function useDemo() {
  const state = useContext(DemoContext);
  if (!state) throw new Error("Demo provider is missing");
  return state;
}
