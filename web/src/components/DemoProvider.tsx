"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import type { Answers, QuestionId } from "@/lib/questions";

type DemoState = {
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
  const [answers, setAnswers] = useState<Answers>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [requested, setRequested] = useState(false);
  return <DemoContext.Provider value={{
    answers,
    answer: (id, value) => {
      setAnswers(previous => ({ ...previous, [id]: value }));
      setSelectedId(null); setRequested(false);
    },
    selectedId,
    select: id => { setSelectedId(id); setRequested(false); },
    requested,
    request: () => setRequested(true),
    reset: () => { setAnswers({}); setSelectedId(null); setRequested(false); },
  }}>{children}</DemoContext.Provider>;
}

export function useDemo() {
  const state = useContext(DemoContext);
  if (!state) throw new Error("Demo provider is missing");
  return state;
}
