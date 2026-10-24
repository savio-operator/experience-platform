"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useDemo } from "./DemoProvider";
import { questions } from "@/lib/questions";
import { parseBudget, fitsBudget } from "@/lib/budget";
import { discoveryEvents, formatMoney, options } from "@/lib/fixtures";
import Photo from "./Photo";
import s from "./chat.module.css";

const ideas = [
  { icon: "↗", text: "Find me something to do in Kochi tonight" },
  { icon: "♡", text: "Help me plan a relaxed date in Kochi" },
  { icon: "✳", text: "I want to plan a birthday surprise" },
];
const MAX_LENGTH = 1000;

export default function ChatPlanner() {
  const demo = useDemo();
  const { chat, setChat } = demo;
  const input = useRef<HTMLTextAreaElement>(null);
  const thread = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  const question = questions[chat.questionIndex];
  const finished = chat.questionIndex >= questions.length;
  const inspiration = discoveryEvents.find(event => event.id === demo.inspirationId);

  useEffect(() => {
    if (thread.current) thread.current.scrollTop = thread.current.scrollHeight;
  }, [chat.messages.length]);

  useEffect(() => {
    if (!input.current) return;
    input.current.style.height = "auto";
    input.current.style.height = `${Math.min(input.current.scrollHeight, 180)}px`;
  }, [chat.draft]);

  function suggest(text: string) {
    const draft = chat.draft.trim() ? `${chat.draft.trim()} ${text}` : text;
    if (draft.length > MAX_LENGTH) {
      setError("Your draft is full. Shorten it before adding another idea.");
      input.current?.focus();
      return;
    }
    setChat(previous => ({ ...previous, draft }));
    setError("");
    input.current?.focus();
    // Keep the caret after the suggestion so the next words extend the idea.
    requestAnimationFrame(() => input.current?.setSelectionRange(draft.length, draft.length));
  }

  function send() {
    const text = chat.draft.trim();
    if (!text || finished) return;
    const parsedBudget = parseBudget(text, question?.type === "budget");
    if (question?.type === "budget" && parsedBudget === null) {
      setError("Give one total budget in whole rupees between ₹1 and ₹10,00,000, like ₹500 or 500 rupees.");
      input.current?.focus();
      return;
    }
    const initialBudget = chat.questionIndex === -1 ? parsedBudget : null;
    if (question) demo.answer(question.id, question.type === "budget" ? parsedBudget! : text);
    if (initialBudget !== null) demo.answer("budget", initialBudget);
    let nextIndex = chat.questionIndex + 1;
    if (questions[nextIndex]?.id === "budget" && (initialBudget ?? demo.answers.budget)) nextIndex++;
    const next = questions[nextIndex];
    const acknowledgement = initialBudget !== null ? `I’ve noted ${formatMoney(initialBudget)} as your total budget. ${options.some(item => fitsBudget(item, initialBudget)) ? "" : "None of the current priced samples fits that budget; I won’t increase it or invent a quote. "}` : "";
    const reply = next
      ? `${acknowledgement}${chat.questionIndex === -1 ? "Let’s shape your idea into a brief. " : ""}${next.title} ${next.hint}`
      : "Your brief is ready. I’ll show available demo samples within your total budget, or explain if none fit. Group size, timing and other needs still require verification. Nothing has been booked.";
    setChat(previous => ({
      ...previous, draft: "", idea: previous.idea || text, questionIndex: nextIndex,
      messages: [...previous.messages, { role: "user", text }, { role: "assistant", text: reply }],
    }));
    setError("");
    input.current?.focus();
  }

  return <section className={s.planner} aria-labelledby="chat-title">
    <div className={s.intro}>
      <div className={s.symbol} aria-hidden="true">✳</div>
      <p className={s.eyebrow}>A LITTLE ELSEWHERE, TOGETHER</p>
      <h1 id="chat-title">What would make<br /><em>today a good day?</em></h1>
      <p>Tell me what you have in mind. A tiny idea is a good place to start.</p>
    </div>
    <div className={s.chat}>
      <div className={s.chatHeader}>
        <span className={s.identity}><span className={s.avatar} aria-hidden="true">e.</span><span>Elsewhere<span className={s.identityHint}>Your Kochi planning companion</span></span></span>
        <span className={s.demoBadge}>Chat preview</span>
      </div>
      {inspiration && <div className={s.inspiration}>
        <div className={s.inspirationPhoto}><Photo id={inspiration.photo} sizes="64px" /></div>
        <div><span>INSPIRATION FROM DISCOVER</span><Link href={`/discover/${inspiration.id}`}>{inspiration.title}</Link><small>Added to your brief · sample event</small></div>
        <button type="button" aria-label="Remove discovery inspiration" onClick={() => demo.setInspirationId(null)}>×</button>
      </div>}
      <div ref={thread} className={s.thread} role="log" aria-label="Planning conversation" aria-live="polite" aria-relevant="additions">
        <div className={s.assistant}>
          <span className={s.speaker}>Elsewhere</span>
          <p>Hey, let’s make a little room for something good. What are you in the mood for in Kochi, now or tonight? Tell me your idea, or find a little inspiration in Discover.</p>
        </div>
        {chat.messages.map((item, index) => <div key={index} className={item.role === "user" ? s.user : s.assistant}>
          <span className={s.speaker}>{item.role === "user" ? "You" : "Elsewhere"}</span>
          <p>{item.text}</p>
        </div>)}
      </div>
      {!finished ? <div className={s.composeArea}>
        <form className={s.composer} onSubmit={event => { event.preventDefault(); send(); }}>
          <label className={s.srOnly} htmlFor="chat-message">Message Elsewhere</label>
          <textarea id="chat-message" ref={input} rows={2} maxLength={MAX_LENGTH}
            placeholder={question?.type === "budget" ? "Your total budget in rupees, e.g. 3000" : "An idea, a mood, a ‘what if’…"}
            value={chat.draft} enterKeyHint="send" aria-invalid={Boolean(error)} aria-describedby="chat-help chat-error"
            onChange={event => { setChat(previous => ({ ...previous, draft: event.target.value })); setError(""); }}
            onKeyDown={event => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.nativeEvent.keyCode !== 229) {
                event.preventDefault(); send();
              }
            }} />
          <div className={s.composerBottom}>
            <span id="chat-help">Enter to send · Shift + Enter for a new line</span>
            <button type="submit" className={s.send} disabled={!chat.draft.trim()} aria-label="Send message"><span aria-hidden="true">↑</span></button>
          </div>
        </form>
        <p id="chat-error" className={s.error} role="alert">{error}</p>
        <div className={s.suggestions} aria-label={question ? "Suggested replies" : "Suggested plan ideas"}>
          <span className={s.suggestionLabel}>{question ? "A starting point" : "Or start with a little inspiration"}</span>
          <div>{(question?.choices || (question ? [] : ideas.map(idea => idea.text))).map((text, index) =>
            <button type="button" key={text} onClick={() => suggest(text)} className={s.suggestion} disabled={!question && index > 0}>
              {!question && <span aria-hidden="true">{ideas[index].icon}</span>}{text}{!question && index > 0 ? <span className={s.comingSoon}>Coming soon</span> : <span aria-hidden="true" className={s.suggestionArrow}>↗</span>}
            </button>
          )}</div>
        </div>
      </div> : <div className={s.finished}>
        <Link href="/brief" className={s.review}>Review my brief <span aria-hidden="true">→</span></Link>
        <button type="button" onClick={() => { demo.reset(); setError(""); }}>Start a new plan</button>
      </div>}
    </div>
    <p className={s.disclosure}>Demo conversation · Scripted replies, not live AI. No availability checks or bookings.</p>
    <Link className={s.guided} href="/questions/when">Prefer a few simple questions? Take it step by step ↗</Link>
    <section className={s.discoveryTeaser} aria-labelledby="chat-discover-title">
      <div className={s.teaserHeading}><h2 id="chat-discover-title">Not sure yet? Look around.</h2><Link href="/discover">Discover Kochi ↗</Link></div>
      <div className={s.teaserGrid}>{discoveryEvents.slice(0, 3).map(event => <Link key={event.id} href={`/discover/${event.id}`} className={s.teaserCard}>
        <div className={s.teaserPhoto}><Photo id={event.photo} sizes="(max-width: 600px) 33vw, 250px" /></div>
        <span>{event.category}</span><strong>{event.title}</strong><small>Sample idea · {event.area}</small>
      </Link>)}</div>
    </section>
  </section>;
}
