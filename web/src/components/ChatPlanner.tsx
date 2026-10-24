"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useDemo } from "./DemoProvider";
import ChatHistory from "./ChatHistory";
import { appendStarter, isFollowUpQuestion } from "@/lib/chat-input";
import { questions, isComplete, type QuestionId } from "@/lib/questions";
import { parseBudget, fitsBudget } from "@/lib/budget";
import { chatStarters, discoveryEvents, formatMoney, options } from "@/lib/fixtures";
import { conversationTitle, type ChatMessage } from "@/lib/chat-history";
import { parseChatReply, recentContext } from "@/lib/chat-protocol";
import Photo from "./Photo";
import s from "./chat.module.css";

const MAX_LENGTH = 4000;

export default function ChatPlanner({ startingQuestion }: { startingQuestion?: QuestionId }) {
  const demo = useDemo();
  const router = useRouter();
  const { chat, setChat, ready, activeId, updateConversation } = demo;
  const input = useRef<HTMLTextAreaElement>(null);
  const thread = useRef<HTMLDivElement>(null);
  const suggestions = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const activeRef = useRef(activeId);
  const openedQuestion = useRef("");
  const sending = useRef(false);
  const [error, setError] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [ai, setAi] = useState<"checking" | "online" | "offline" | "unreachable">("checking");
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [retry, setRetry] = useState<{ chatId: string; messages: ChatMessage[] } | null>(null);
  const question = questions[chat.questionIndex];
  const finished = isComplete(demo.answers);
  const inspiration = discoveryEvents.find(event => event.id === demo.inspirationId);
  activeRef.current = activeId;

  useEffect(() => {
    const abort = new AbortController();
    fetch("/api/chat", { signal: AbortSignal.any([abort.signal, AbortSignal.timeout(10000)]), cache: "no-store" })
      .then(async response => { if (!response.ok) throw new Error(); return response.json(); })
      .then(status => setAi(status.available === true ? "online" : "offline"))
      .catch(() => { if (!abort.signal.aborted) setAi("unreachable"); });
    return () => abort.abort();
  }, []);

  useEffect(() => {
    if (!ready || !startingQuestion || openedQuestion.current === `${activeId}:${startingQuestion}`) return;
    openedQuestion.current = `${activeId}:${startingQuestion}`;
    const index = questions.findIndex(item => item.id === startingQuestion);
    const next = questions[index];
    if (!next) return;
    setChat(previous => ({ ...previous, questionIndex: index,
      messages: [...previous.messages, { role: "assistant", source: "demo", text: `Let’s update your brief. ${next.title} ${next.hint}` }],
    }));
    input.current?.focus();
  }, [startingQuestion, setChat, ready, activeId]);

  useEffect(() => { setError(""); nearBottom.current = true; }, [activeId]);
  useEffect(() => {
    if (thread.current && nearBottom.current) thread.current.scrollTop = thread.current.scrollHeight;
  }, [chat.messages.length, activeId, pendingId]);
  useEffect(() => {
    if (!input.current) return;
    input.current.style.height = "auto";
    input.current.style.height = `${Math.min(input.current.scrollHeight, 180)}px`;
  }, [chat.draft]);

  async function askAI(chatId: string, messages: ChatMessage[]) {
    if (sending.current) return;
    sending.current = true;
    setPendingId(chatId); setError(""); setRetry(null);
    try {
      const conversation = demo.conversations.find(item => item.id === chatId);
      const response = await fetch("/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: recentContext(messages), answers: conversation?.answers || {} }),
        signal: AbortSignal.timeout(45000),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.error === "string" ? data.error : "The reply didn’t arrive. Please try again.");
      const reply = parseChatReply(data);
      if (!reply) throw new Error("The reply couldn’t be read. Your message is saved; please try again.");
      updateConversation(chatId, previous => {
        const answers = { ...previous.answers, ...reply.preferences };
        const changed = Object.keys(reply.preferences).length > 0;
        return { ...previous, answers, ...(changed ? { selectedId: null, requested: false } : {}), chat: { ...previous.chat,
          questionIndex: isComplete(answers) ? questions.length : questions.findIndex(item => !answers[item.id]),
          messages: [...previous.chat.messages, { role: "assistant", text: reply.reply, source: "openai" }],
        } };
      });
    } catch (failure) {
      setRetry({ chatId, messages });
      if (activeRef.current === chatId) setError(failure instanceof Error && failure.name !== "TimeoutError" ? failure.message : "The reply timed out. Your message is saved. You can retry.");
    } finally {
      sending.current = false; setPendingId(null);
    }
  }

  function addStarter(text: string) {
    const draft = appendStarter(chat.draft, text, MAX_LENGTH);
    if (draft === null) {
      setError("Your message is nearly full. Shorten it before adding an idea.");
      suggestions.current?.hidePopover();
      input.current?.focus();
      return;
    }
    setChat(previous => ({ ...previous, draft }));
    setError("");
    suggestions.current?.hidePopover();
    requestAnimationFrame(() => {
      input.current?.focus();
      input.current?.setSelectionRange(draft.length, draft.length);
    });
  }

  function send() {
    const text = chat.draft.trim();
    if (!text || !ready || sending.current || ai === "checking") return;
    nearBottom.current = true;
    if (ai === "online") {
      const messages: ChatMessage[] = [...chat.messages, { role: "user", text }];
      setChat(previous => ({ ...previous, draft: "", idea: previous.idea || text, messages }));
      void askAI(activeId, messages);
      return;
    }
    // Explicit demo guide only; never pretend scripted text is an AI response.
    if (isFollowUpQuestion(text) || (finished && !question)) {
      const reply = "Live AI isn’t connected yet, so I can’t answer that here. Your message is saved and your preferences haven’t changed. You can continue a demo plan by sharing your preferences, or return when AI is connected.";
      setChat(previous => ({ ...previous, draft: "", idea: previous.idea || text, messages: [...previous.messages, { role: "user", text }, { role: "assistant", text: reply, source: "demo" }] }));
      setError(""); return;
    }
    const parsedBudget = parseBudget(text, question?.type === "budget");
    if (question?.type === "budget" && parsedBudget === null) {
      setError("Give one total budget in whole rupees between ₹1 and ₹10,00,000, like ₹500 or 500 rupees."); return;
    }
    const initialBudget = chat.questionIndex === -1 ? parsedBudget : null;
    if (question) demo.answer(question.id, question.type === "budget" ? parsedBudget! : text);
    if (initialBudget !== null) demo.answer("budget", initialBudget);
    const updatedAnswers = { ...demo.answers, ...(question ? { [question.id]: question.type === "budget" ? parsedBudget! : text } : {}), ...(initialBudget !== null ? { budget: initialBudget } : {}) };
    let nextIndex = isComplete(updatedAnswers) ? questions.length : chat.questionIndex + 1;
    if (questions[nextIndex]?.id === "budget" && (initialBudget ?? demo.answers.budget)) nextIndex++;
    const next = questions[nextIndex];
    const acknowledgement = initialBudget !== null ? `I’ve noted ${formatMoney(initialBudget)} as your total budget. ${options.some(item => fitsBudget(item, initialBudget)) ? "" : "None of the priced samples fits that budget; I won’t change it or invent a quote. "}` : "";
    const reply = next ? `${acknowledgement}${next.title} ${next.hint}` : "Your demo brief is ready to review. Sample options are checked against your budget. Other requirements still need verification. Nothing has been booked.";
    setChat(previous => ({ ...previous, draft: "", idea: previous.idea || text, questionIndex: nextIndex,
      messages: [...previous.messages, { role: "user", text }, { role: "assistant", text: reply, source: "demo" }],
    }));
    setRetry(null); setError(""); input.current?.focus();
    if (startingQuestion === "budget" && question?.id === "budget" && isComplete(updatedAnswers)) router.replace("/options");
  }

  function download() {
    const conversation = demo.conversations.find(item => item.id === activeId);
    if (!conversation) return;
    const body = `${conversationTitle(conversation)}\nDemo conversation · no real booking or payment\n\n${chat.messages.map(message => `${message.role === "user" ? "You" : message.source === "openai" ? "Elsewhere · AI" : "Elsewhere · Demo guide"}\n${message.text}`).join("\n\n")}\n\n${chat.draft ? `Unsent draft\n${chat.draft}` : ""}`;
    const url = URL.createObjectURL(new Blob([body], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = `elsewhere-${conversation.id}.txt`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <div className={s.workspace}>
    <div className={s.mobileToolbar}><button type="button" aria-expanded={historyOpen} aria-controls="conversation-history" onClick={() => setHistoryOpen(!historyOpen)}>{historyOpen ? "Close history" : "Chat history"}</button><button disabled={!ready} onClick={() => { demo.newChat(); setHistoryOpen(false); }}>＋ New chat</button></div>
    <div id="conversation-history" className={`${s.history} ${historyOpen ? s.historyOpen : ""}`}><ChatHistory onNavigate={() => { setHistoryOpen(false); input.current?.focus(); }} /></div>
    <section className={s.planner} aria-labelledby="chat-title">
      <div className={s.intro}>
        <div className={s.introPhoto}><Photo id="water" sizes="(max-width: 850px) 90vw, 760px" eager /></div>
        <p className={s.eyebrow}>A LITTLE ELSEWHERE, IN YOUR OWN WORDS</p>
        <h1 id="chat-title">Where shall we go?</h1>
        <p>An idea, a question, a change of plans. Start anywhere.</p>
      </div>
      {demo.storageWarning && <p className={s.notice} role="status">{demo.storageWarning}</p>}
      <div className={s.chat}>
        <div className={s.chatHeader}>
          <span className={s.identity}><span className={s.avatar}><Photo id="water" sizes="40px" /></span><span>Elsewhere<span className={s.identityHint}>Room for whatever’s on your mind</span></span></span>
          <span className={s.demoBadge}>{ai === "checking" ? "Connecting…" : ai === "online" ? "OpenAI" : "Demo guide · AI offline"}</span>
        </div>
        {inspiration && <div className={s.inspiration}><div className={s.inspirationPhoto}><Photo id={inspiration.photo} sizes="64px" /></div><div><span>INSPIRATION FROM DISCOVER</span><Link href={`/discover/${inspiration.id}`}>{inspiration.title}</Link><small>Sample event · not reserved</small></div><button type="button" aria-label="Remove discovery inspiration" onClick={() => demo.setInspirationId(null)}>×</button></div>}
        <div ref={thread} className={s.thread} role="log" aria-label="Conversation" aria-live="polite" aria-relevant="additions" tabIndex={0} onScroll={() => { const node = thread.current; if (node) nearBottom.current = node.scrollHeight - node.scrollTop - node.clientHeight < 80; }}>
          <div className={s.assistant}><span className={s.speaker}>Elsewhere</span><p>{!ready ? "Opening your conversation…" : "Hey, what’s on your mind? We can dream up a day in Kochi, talk through an idea, or pick up where we left off."}</p></div>
          {chat.messages.map((item, index) => <div key={index} className={item.role === "user" ? s.user : s.assistant}><span className={s.speaker}>{item.role === "user" ? "You" : item.source === "openai" ? "Elsewhere · AI" : "Elsewhere · Demo guide"}</span><p>{item.text}</p></div>)}
          {pendingId === activeId && <p className={s.thinking} role="status">Thinking… You can keep reading your conversation.</p>}
        </div>
        <div className={s.composeArea}>
          <form className={s.composer} onSubmit={event => { event.preventDefault(); send(); }}>
            <label className={s.srOnly} htmlFor="chat-message">Message Elsewhere</label>
            <textarea id="chat-message" ref={input} rows={2} maxLength={MAX_LENGTH} disabled={!ready} placeholder="Tell me what’s on your mind…" value={chat.draft} enterKeyHint="send" aria-invalid={Boolean(error)} aria-describedby="chat-help chat-error" onChange={event => { setChat(previous => ({ ...previous, draft: event.target.value })); setError(""); }} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.nativeEvent.keyCode !== 229) { event.preventDefault(); send(); } }} />
            <div className={s.composerBottom}><span id="chat-help">Enter to send · Shift + Enter for a new line</span><button type="submit" className={s.send} disabled={!ready || !chat.draft.trim() || Boolean(pendingId) || ai === "checking"} aria-label="Send message"><span aria-hidden="true">↑</span></button></div>
          </form>
          <p id="chat-error" className={s.error} role="alert">{error}</p>
          {chat.questionIndex === -1 && <>
            <button type="button" disabled={!ready} className={s.suggestionTrigger} popoverTarget="plan-suggestions">✳ Need an idea?</button>
            <div id="plan-suggestions" ref={suggestions} popover="auto" className={s.starters} role="dialog" aria-labelledby="suggestion-title">
              <header><strong id="suggestion-title">A little inspiration</strong><button type="button" popoverTarget="plan-suggestions" popoverTargetAction="hide" aria-label="Close suggestions">×</button></header>
              <p>Pick an idea, then make it your own in the chat box.</p>
              <div>{chatStarters.map(starter => <button key={starter.id} type="button" onClick={() => addStarter(starter.text)}>
                <span aria-hidden="true">{starter.icon}</span><span>{starter.text}</span><span aria-hidden="true">↗</span>
              </button>)}</div>
            </div>
          </>}
          {retry?.chatId === activeId && <button className={s.textButton} disabled={Boolean(pendingId)} onClick={() => { nearBottom.current = true; void askAI(retry.chatId, retry.messages); }}>Retry reply</button>}
          <div className={s.conversationActions}><span>{demo.storageWarning ? "Browser storage needs attention" : "Saved in this browser"}</span><button className={s.textButton} disabled={!ready || (!chat.messages.length && !chat.draft)} onClick={download}>Download chat ↓</button></div>
        </div>
        {finished && <div className={s.finished}><Link href="/brief" className={s.review}>Review my brief <span aria-hidden="true">→</span></Link></div>}
      </div>
      <p className={s.disclosure}>{ai === "online" ? "Messages and planning preferences are sent to OpenAI for replies. Recent messages provide context; your full history stays in this browser. AI can make mistakes. No live availability checks or bookings." : "Live AI is not connected. The demo guide can collect planning preferences but cannot answer general questions. Chats stay in this browser; clearing browser data removes them."}</p>
      <section className={s.discoveryTeaser} aria-labelledby="chat-discover-title"><div className={s.teaserHeading}><h2 id="chat-discover-title">A little inspiration nearby.</h2><Link href="/discover">Discover Kochi ↗</Link></div><div className={s.teaserGrid}>{discoveryEvents.slice(0, 3).map(event => <Link key={event.id} href={`/discover/${event.id}`} className={s.teaserCard}><div className={s.teaserPhoto}><Photo id={event.photo} sizes="(max-width: 600px) 33vw, 250px" /></div><span>{event.category}</span><strong>{event.title}</strong><small>Sample idea · {event.area}</small></Link>)}</div></section>
    </section>
  </div>;
}
