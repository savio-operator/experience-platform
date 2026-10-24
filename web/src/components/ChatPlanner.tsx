"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useDemo } from "./DemoProvider";
import { appendStarter, isFollowUpQuestion } from "@/lib/chat-input";
import { questions, type QuestionId } from "@/lib/questions";
import { parseBudget, fitsBudget } from "@/lib/budget";
import { chatStarters, discoveryEvents, formatMoney, options } from "@/lib/fixtures";
import Photo from "./Photo";
import s from "./chat.module.css";

const MAX_LENGTH = 1000;

export default function ChatPlanner({ startingQuestion }: { startingQuestion?: QuestionId }) {
  const demo = useDemo();
  const { chat, setChat } = demo;
  const input = useRef<HTMLTextAreaElement>(null);
  const thread = useRef<HTMLDivElement>(null);
  const openedQuestion = useRef<QuestionId | undefined>(undefined);
  const [error, setError] = useState("");
  const question = questions[chat.questionIndex];
  const finished = chat.questionIndex >= questions.length;
  const inspiration = discoveryEvents.find(event => event.id === demo.inspirationId);

  useEffect(() => {
    if (!startingQuestion || openedQuestion.current === startingQuestion) return;
    openedQuestion.current = startingQuestion;
    const index = questions.findIndex(item => item.id === startingQuestion);
    const next = questions[index];
    if (!next) return;
    setChat(previous => ({ ...previous, questionIndex: index,
      messages: [...previous.messages, { role: "assistant", text: `${next.title} ${next.hint}` }],
    }));
    input.current?.focus();
  }, [startingQuestion, setChat]);

  useEffect(() => {
    if (thread.current) thread.current.scrollTop = thread.current.scrollHeight;
  }, [chat.messages.length]);

  useEffect(() => {
    if (!input.current) return;
    input.current.style.height = "auto";
    input.current.style.height = `${Math.min(input.current.scrollHeight, 180)}px`;
  }, [chat.draft]);

  function addStarter(text: string) {
    const draft = appendStarter(chat.draft, text, MAX_LENGTH);
    if (draft === null) {
      setError("Your message is nearly full. Shorten it before adding an idea.");
      input.current?.focus();
      return;
    }
    setChat(previous => ({ ...previous, draft }));
    setError("");
    requestAnimationFrame(() => {
      input.current?.focus();
      input.current?.setSelectionRange(draft.length, draft.length);
    });
  }

  function send() {
    const text = chat.draft.trim();
    if (!text) return;
    if ((question && isFollowUpQuestion(text)) || finished) {
      const reply = finished
        ? "Your brief is ready to review. You can edit a preference from the brief. Live AI isn’t connected yet, so I can’t answer general questions in this preview."
        : `Live AI isn’t connected yet, so I can’t answer general questions in this preview. I haven’t changed your preferences. ${question ? `${question.title} ${question.hint}` : "What would you like to plan in Kochi?"}`;
      setChat(previous => ({ ...previous, draft: "", messages: [...previous.messages, { role: "user", text }, { role: "assistant", text: reply }] }));
      setError("");
      input.current?.focus();
      return;
    }
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
      ...previous, draft: "", idea: previous.idea || (chat.questionIndex === -1 ? text : ""), questionIndex: nextIndex,
      messages: [...previous.messages, { role: "user", text }, { role: "assistant", text: reply }],
    }));
    setError("");
    input.current?.focus();
  }

  return <section className={s.planner} aria-labelledby="chat-title">
    <div className={s.intro}>
      <div className={s.orb} aria-hidden="true"><span /></div>
      <p className={s.eyebrow}>A LITTLE ELSEWHERE, IN YOUR OWN WORDS</p>
      <h1 id="chat-title">Your day.<br /><em>Your way.</em></h1>
      <p>No boxes to tick. Just tell me what you have in mind.</p>
    </div>
    <div className={s.chat}>
      <div className={s.chatHeader}>
        <span className={s.identity}><span className={s.avatar} aria-hidden="true" /><span>Elsewhere<span className={s.identityHint}>A little space to make a plan</span></span></span>
        <span className={s.demoBadge}>Preview · AI offline</span>
      </div>
      {inspiration && <div className={s.inspiration}>
        <div className={s.inspirationPhoto}><Photo id={inspiration.photo} sizes="64px" /></div>
        <div><span>INSPIRATION FROM DISCOVER</span><Link href={`/discover/${inspiration.id}`}>{inspiration.title}</Link><small>Added to your brief · sample event</small></div>
        <button type="button" aria-label="Remove discovery inspiration" onClick={() => demo.setInspirationId(null)}>×</button>
      </div>}
      <div ref={thread} className={s.thread} role="log" aria-label="Planning conversation" aria-live="polite" aria-relevant="additions">
        <div className={s.assistant}>
          <span className={s.speaker}>Elsewhere</span>
          <p>Hey, what would you like to do in Kochi? Tell me your idea, your own timing, or a preference you’d like me to keep in mind.</p>
        </div>
        {chat.messages.map((item, index) => <div key={index} className={item.role === "user" ? s.user : s.assistant}>
          <span className={s.speaker}>{item.role === "user" ? "You" : "Elsewhere"}</span>
          <p>{item.text}</p>
        </div>)}
      </div>
      <div className={s.composeArea}>
        {question && <p className={s.currentQuestion}><span>WE’RE PLANNING</span>{question.title}</p>}
        <form className={s.composer} onSubmit={event => { event.preventDefault(); send(); }}>
          <label className={s.srOnly} htmlFor="chat-message">Message Elsewhere</label>
          <textarea id="chat-message" ref={input} rows={2} maxLength={MAX_LENGTH}
            placeholder={question?.placeholder || "Tell me what’s on your mind…"}
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
        {chat.questionIndex === -1 && <div className={s.starters} role="group" aria-label="Suggested plan ideas">
          <p>Or start with a little inspiration. Add an idea, then make it your own.</p>
          <div>{chatStarters.map(starter => <button key={starter.id} type="button" onClick={() => addStarter(starter.text)}>
            <span aria-hidden="true">{starter.icon}</span><span>{starter.text}</span><span aria-hidden="true">↗</span>
          </button>)}</div>
        </div>}
      </div>
      {finished && <div className={s.finished}>
        <Link href="/brief" className={s.review}>Review my brief <span aria-hidden="true">→</span></Link>
        <button type="button" onClick={() => { demo.reset(); setError(""); }}>Start a new plan</button>
      </div>}
    </div>
    <p className={s.disclosure}>Preview · Preferences are saved in this tab. Live AI replies aren’t connected. No availability checks or bookings.</p>
    <section className={s.discoveryTeaser} aria-labelledby="chat-discover-title">
      <div className={s.teaserHeading}><h2 id="chat-discover-title">Not sure yet? Look around.</h2><Link href="/discover">Discover Kochi ↗</Link></div>
      <div className={s.teaserGrid}>{discoveryEvents.slice(0, 3).map(event => <Link key={event.id} href={`/discover/${event.id}`} className={s.teaserCard}>
        <div className={s.teaserPhoto}><Photo id={event.photo} sizes="(max-width: 600px) 33vw, 250px" /></div>
        <span>{event.category}</span><strong>{event.title}</strong><small>Sample idea · {event.area}</small>
      </Link>)}</div>
    </section>
  </section>;
}
