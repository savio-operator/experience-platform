"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useDemo } from "./DemoProvider";
import { questions, isComplete } from "@/lib/questions";
import { intents, options, timeline, formatMoney, formatTime, type DemoOption } from "@/lib/fixtures";
import s from "./demo.module.css";

type PreviewState = "ready" | "loading" | "empty" | "error";
const stages = ["Your idea", "The brief", "Your options", "Your request"];

function Scene({ kind, large = false }: { kind: DemoOption["art"]; large?: boolean }) {
  return <div className={`${s.scene} ${s[kind]} ${large ? s.sceneLarge : ""}`} aria-hidden="true">
    <span className={s.sun} /><span className={s.horizon} /><span className={s.shapeOne} /><span className={s.shapeTwo} /><span className={s.shapeThree} />
    <span className={s.artCaption}>{kind === "water" ? "THE WATERFRONT EDIT" : kind === "clay" ? "MAKE SOMETHING OF TODAY" : "PULL UP A CHAIR"}</span>
  </div>;
}

function Status({ option }: { option: DemoOption }) {
  return <span className={`${s.badge} ${option.availability === "UNAVAILABLE" ? s.unavailable : ""}`}><span aria-hidden="true">●</span> {option.availability === "UNAVAILABLE" ? "Unavailable" : "Available in demo"}</span>;
}

function Heading({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return <div className={s.heading}><p className={s.eyebrow}>{eyebrow}</p><h1>{title}</h1>{children && <p className={s.subtitle}>{children}</p>}</div>;
}

function Empty({ title = "Nothing here just yet", children, href = "/", action = "Start planning" }: { title?: string; children: ReactNode; href?: string; action?: string }) {
  return <div className={s.statePanel}><span className={s.stateIcon} aria-hidden="true">↗</span><h2>{title}</h2><p>{children}</p><Link className={s.primary} href={href}>{action} <span aria-hidden="true">→</span></Link></div>;
}

export default function DemoScreen({ path = "" }: { path?: string }) {
  const demo = useDemo();
  const router = useRouter();
  const [preview, setPreview] = useState<PreviewState>("ready");
  const [budgetText, setBudgetText] = useState(demo.answers.budget ? String(demo.answers.budget / 100) : "");
  const [message, setMessage] = useState("");
  const headingRef = useRef<HTMLElement>(null);
  const questionId = path.startsWith("questions/") ? path.split("/")[1] : null;
  const questionIndex = questions.findIndex(question => question.id === questionId);
  const question = questions[questionIndex];
  const option = path.startsWith("options/") ? options.find(item => item.id === path.split("/")[1]) : undefined;
  const selected = options.find(item => item.id === demo.selectedId);
  const complete = isComplete(demo.answers);
  const stage = path === "brief" ? 1 : path.startsWith("options") ? 2 : path === "checkout" || path === "booking" ? 3 : 0;

  useEffect(() => {
    setPreview("ready"); setMessage("");
    setBudgetText(demo.answers.budget ? String(demo.answers.budget / 100) : "");
    headingRef.current?.focus({ preventScroll: true });
    // Route changes retain the provider's answers, but clear simulated state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path]);

  const back = question ? questionIndex === 0 ? "/" : `/questions/${questions[questionIndex - 1].id}`
    : path === "brief" ? "/questions/transport"
    : option ? "/options"
    : path === "options" ? "/brief"
    : path === "checkout" && selected ? `/options/${selected.id}` : "/";

  function nextQuestion() {
    if (!question) return;
    if (question.id === "budget") {
      if (!/^\d+$/.test(budgetText) || Number(budgetText) < 1 || Number(budgetText) > 1_000_000) {
        setMessage("Enter a whole-rupee budget between ₹1 and ₹10,00,000."); return;
      }
      demo.answer("budget", Number(budgetText) * 100);
    } else if (!String(demo.answers[question.id] ?? "").trim()) {
      setMessage("Please add an answer before continuing."); return;
    }
    setMessage("");
    router.push(questionIndex === questions.length - 1 ? "/brief" : `/questions/${questions[questionIndex + 1].id}`);
  }

  let content: ReactNode;
  if (!path) {
    content = <>
      <div className={s.hero}>
        <div><p className={s.eyebrow}><span className={s.smallLine} /> LESS PLANNING. MORE LIVING.</p><h1>Good evenings<br />start with a<br /><span className={s.softWord}>little idea.</span><span className={s.spark} aria-hidden="true">✳</span></h1><p className={s.heroCopy}>A change of scenery. Something new to try.<br />Let’s find your kind of good time in Kochi.</p><div className={s.heroNote}><span className={s.noteIcon} aria-hidden="true">↗</span><span>A few questions.<br /><strong>A plan that feels like you.</strong></span></div></div>
        <div className={s.heroArt}><Scene kind="water" large /><span className={s.postcard}>a little<br /><em>elsewhere.</em></span><span className={s.artTag}>9.9312° N · 76.2673° E</span></div>
      </div>
      <div className={s.sectionLabel}><h2>What brings you here?</h2><span>ONE SMALL IDEA IS ALL IT TAKES</span></div>
      <div className={s.intentGrid}>{intents.map(intent => <button key={intent.id} className={`${s.intent} ${intent.enabled ? s.activeIntent : ""}`} disabled={!intent.enabled} onClick={() => router.push("/questions/when")}><span className={s.intentIcon} aria-hidden="true">{intent.icon}</span><span className={s.intentText}><strong>{intent.title}</strong><span>{intent.subtitle}</span></span><span className={s.intentEnd}>{intent.enabled ? <span aria-hidden="true">↗</span> : "Coming soon"}</span></button>)}</div>
    </>;
  } else if (question) {
    const value = demo.answers[question.id];
    content = <div className={s.narrow}><div className={s.questionTop}><span>YOUR EVENING, YOUR WAY</span><span>{String(questionIndex + 1).padStart(2, "0")} / 08</span></div><div className={s.progress}><span style={{ width: `${(questionIndex + 1) / questions.length * 100}%` }} /></div><Heading eyebrow={`QUESTION ${questionIndex + 1}`} title={question.title}>{question.hint}</Heading>
      <form onSubmit={event => { event.preventDefault(); nextQuestion(); }}>
        {question.type === "choice" && <fieldset className={s.choices}><legend className={s.srOnly}>{question.title}</legend>{question.choices?.map(choice => <label key={choice} className={`${s.choice} ${value === choice ? s.chosen : ""}`}><input type="radio" name={question.id} value={choice} checked={value === choice} onChange={() => { demo.answer(question.id, choice); setMessage(""); }} /><span>{choice}</span><span className={s.radio} aria-hidden="true">{value === choice ? "●" : ""}</span></label>)}</fieldset>}
        {question.type === "budget" && <><label className={s.inputLabel} htmlFor="budget">Total budget in rupees</label><div className={s.moneyInput}><span aria-hidden="true">₹</span><input id="budget" inputMode="numeric" autoComplete="off" placeholder="e.g. 3000" value={budgetText} onChange={event => { const raw = event.target.value; setBudgetText(raw); demo.answer("budget", /^\d+$/.test(raw) && Number(raw) <= 1_000_000 ? Number(raw) * 100 : 0); setMessage(""); }} aria-describedby={message ? "question-error" : undefined} /></div><p className={s.finePrint}>A spending preference, not a quote or payment.</p></>}
        {question.type === "text" && <><label className={s.inputLabel} htmlFor="constraints">Your needs and exclusions</label><textarea id="constraints" className={s.textarea} maxLength={1000} rows={5} placeholder={question.placeholder} value={String(value ?? "")} onChange={event => { demo.answer(question.id, event.target.value); setMessage(""); }} aria-describedby={message ? "question-error" : undefined} /></>}
        {message && <p id="question-error" className={s.errorMessage} role="alert">{message}</p>}
        <div className={s.formFooter}><span>You can change this later.</span><button className={s.primary} type="submit">{questionIndex === 7 ? "See my brief" : "Continue"}<span aria-hidden="true">→</span></button></div>
      </form></div>;
  } else if (path === "brief") {
    content = complete ? <div className={s.narrow}><Heading eyebrow="THE BRIEF" title="Here’s the evening you have in mind.">A quick check before we explore the possibilities.</Heading><div className={s.briefCard}>
      <div><span className={s.briefNumber}>01</span><h2>What</h2><p>{demo.answers.kind} in {demo.answers.where?.toLowerCase()}.</p><dl><dt>When</dt><dd>{demo.answers.when}</dd><dt>Company</dt><dd>{demo.answers.who}</dd></dl></div>
      <div><span className={s.briefNumber}>02</span><h2>Why</h2><p>{demo.answers.occasion}</p></div>
      <div><span className={s.briefNumber}>03</span><h2>Which</h2><dl><dt>Total budget</dt><dd>{formatMoney(demo.answers.budget!)}</dd><dt>Keep in mind</dt><dd>{demo.answers.constraints}</dd><dt>Getting there</dt><dd>{demo.answers.transport}</dd></dl></div>
    </div><div className={s.actions}><Link className={s.secondary} href="/questions/when">Edit answers</Link><Link className={s.primary} href="/options">Explore options <span aria-hidden="true">→</span></Link></div><p className={s.finePrint}>The next screen shows fixed examples, not recommendations matched to your answers.</p></div> : <Empty href="/questions/when" action="Answer the questions">Finish the eight questions to see your brief. Answers stay here while you move between pages, but reset on refresh.</Empty>;
  } else if (path === "options") {
    content = complete ? <><Heading eyebrow="A FEW POSSIBILITIES" title="Three ways to make an evening.">Illustrative experiences, sample prices, and honest availability. Pick one to take a closer look.</Heading><div className={s.demoNotice}>These are fixed demo fixtures for 24 October 2026. They are not matched to your budget, group, timing, or constraints.</div><div className={s.optionGrid}>{options.map((item, index) => <article key={item.id} className={s.optionCard}><div className={s.cardArt}><Scene kind={item.art} /><span className={s.optionNumber}>0{index + 1}</span></div><div className={s.optionBody}><div className={s.cardMeta}>{item.category} <span>· {item.area}</span></div><h2>{item.title}</h2><Status option={item} /><ul className={s.inclusions}>{item.inclusions.map(inclusion => <li key={inclusion}>{inclusion}</li>)}</ul><div className={s.optionFacts}><span>{item.durationMinutes} min experience</span><span>Travel: {item.travelMinutes === null ? "Not provided" : `${item.travelMinutes} min`}</span></div><p className={s.terms}>{item.cancellationTerms}</p><div className={s.priceRow}><div><strong>{formatMoney(item.pricePaise)}</strong><span>sample total for two</span></div><Link className={s.roundLink} href={`/options/${item.id}`} aria-label={`View ${item.title}`}>↗</Link></div></div></article>)}</div><Link href="/brief" className={s.textLink}>Not your kind of evening? Edit your brief →</Link></> : <Empty href="/questions/when">Start with a few questions to explore the sample options.</Empty>;
  } else if (option) {
    content = complete ? <div className={s.detail}><div><Scene kind={option.art} large /><p className={s.finePrint}>Original illustration · synthetic experience, no real supplier</p></div><div><Heading eyebrow={`${option.category} · ${option.area}`} title={option.title}>{option.description}</Heading><Status option={option} /><p className={s.detailPrice}>{formatMoney(option.pricePaise)} <span>sample total for two</span></p><dl className={s.detailFacts}><dt>Sample start</dt><dd>{formatTime(option.startsAt)} IST</dd><dt>Duration</dt><dd>{option.durationMinutes} minutes</dd><dt>Travel time</dt><dd>{option.travelMinutes === null ? "Not provided" : `${option.travelMinutes} minutes`}</dd></dl><h2 className={s.smallTitle}>A little more included</h2><ul className={s.inclusions}>{option.inclusions.map(item => <li key={item}>{item}</li>)}</ul><div className={s.termsBox}><h3>Cancellation terms</h3><p>{option.cancellationTerms}</p></div><div className={s.actions}><Link className={s.secondary} href="/brief">Customise</Link><button className={s.primary} disabled={option.availability === "UNAVAILABLE"} onClick={() => { demo.select(option.id); router.push("/checkout"); }}>{option.availability === "UNAVAILABLE" ? "Unavailable" : "Proceed"}{option.availability === "AVAILABLE" && <span aria-hidden="true">→</span>}</button></div><p className={s.finePrint}>Sample only. Proceeding does not reserve inventory.</p></div></div> : <Empty href="/questions/when">Complete your brief before choosing a sample experience.</Empty>;
  } else if (path === "checkout") {
    content = selected && complete && selected.availability === "AVAILABLE" ? <div className={s.narrow}><Heading eyebrow="ONE LAST LOOK" title="Your evening, on the page.">This is a payment simulation. No details or money required.</Heading><div className={s.checkoutCard}><Scene kind={selected.art} /><div><span className={s.eyebrow}>{selected.area}</span><h2>{selected.title}</h2><p>{formatTime(selected.startsAt)} IST · {selected.durationMinutes} min</p></div></div><div className={s.total}><span>Sample total for two</span><strong>{formatMoney(selected.pricePaise)}</strong></div><p className={s.terms}>{selected.cancellationTerms}</p><div className={s.demoNotice}>Your answers have not been checked against this sample experience. This button only opens a simulated request status.</div><button className={`${s.primary} ${s.fullWidth}`} onClick={() => { demo.request(); router.push("/booking"); }}>Demo payment <span aria-hidden="true">→</span></button><p className={s.finePrint}>No charge. No payment provider. No reservation.</p></div> : <Empty href={complete ? "/options" : "/questions/when"} action="Choose an experience">Choose an available sample option before opening checkout.</Empty>;
  } else if (path === "booking") {
    content = demo.requested && selected ? <div className={s.narrow}><div className={s.pendingIcon} aria-hidden="true">↗</div><Heading eyebrow="YOUR DEMO REQUEST" title="Requested, awaiting vendor confirmation">A little anticipation. Here’s where your request would stand.</Heading><div className={s.requestSummary}><strong>{selected.title}</strong><span>{formatTime(selected.startsAt)} IST</span><span>Payment: simulated only · no money moved</span></div><ol className={s.timeline}>{timeline.map((event, index) => <li key={event.title} className={event.current ? s.currentEvent : ""}><span className={s.timelineDot} aria-hidden="true">{index === 0 ? "✓" : index === 1 ? "·" : ""}</span><div><h2>{event.title}</h2><p>{event.description}</p></div></li>)}</ol><div className={s.demoNotice}>This status will not advance. No real request, vendor contact, or payment was made.</div><button className={s.secondary} onClick={() => { demo.reset(); router.push("/"); }}>Explore another evening <span aria-hidden="true">↗</span></button></div> : <Empty href={complete ? "/options" : "/"}>There’s no demo request in this session. Follow the flow to create one.</Empty>;
  } else {
    content = <Empty title="A little off the beaten path">This demo page doesn’t exist. Let’s head back to the beginning.</Empty>;
  }

  return <main id="main" ref={headingRef} tabIndex={-1} className={s.main}>
    <div className={s.utilityBar}>{path ? <Link className={s.back} href={back}>← Back</Link> : <span className={s.utilityNote}>THE EVERYDAY ESCAPE CLUB</span>}<label className={s.previewLabel}>Preview state<select aria-label="Simulate screen state" value={preview} onChange={event => setPreview(event.target.value as PreviewState)}><option value="ready">Ready</option><option value="loading">Loading</option><option value="empty">Empty</option><option value="error">Error</option></select></label></div>
    {path && <nav aria-label="Planning progress" className={s.steps}>{stages.map((label, index) => <span key={label} aria-current={stage === index ? "step" : undefined} className={stage === index ? s.currentStep : ""}><i>{index + 1}</i>{label}</span>)}</nav>}
    {preview === "ready" ? content : <div className={s.statePanel} role={preview === "error" ? "alert" : "status"} aria-live="polite">
      <span className={s.stateIcon} aria-hidden="true">{preview === "error" ? "!" : preview === "empty" ? "○" : "···"}</span>
      <h2>{preview === "loading" ? "Getting things ready…" : preview === "empty" ? "Nothing to show just yet" : "That didn’t quite work"}</h2>
      <p>{preview === "loading" ? "Simulated loading. Your answers are safe in this session." : preview === "empty" ? "Simulated empty state. No data is available for this screen." : "Simulated error. No action was submitted and your answers haven’t changed."}</p>
      {preview === "loading" && <div className={s.skeleton} aria-hidden="true"><span /><span /><span /></div>}
      <button className={s.primary} onClick={() => setPreview("ready")}>{preview === "error" ? "Retry" : preview === "loading" ? "Finish demo loading" : "Restore demo content"}<span aria-hidden="true">→</span></button>
    </div>}
  </main>;
}
