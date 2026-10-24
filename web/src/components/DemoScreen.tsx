"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import ChatPlanner from "./ChatPlanner";
import Photo from "./Photo";
import { useDemo } from "./DemoProvider";
import { questions, isComplete } from "@/lib/questions";
import { options, timeline, discoveryEvents, formatMoney, formatTime, type DemoOption } from "@/lib/fixtures";
import { fitsBudget } from "@/lib/budget";
import s from "./demo.module.css";

type PreviewState = "ready" | "loading" | "empty" | "error";
const stages = ["Your idea", "The brief", "Your options", "Your request"];

function Scene({ kind, large = false }: { kind: DemoOption["art"]; large?: boolean }) {
  return <div className={`${s.scene} ${large ? s.sceneLarge : ""}`}>
    <Photo id={kind} eager={large} />
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
  const headingRef = useRef<HTMLElement>(null);
  const questionId = path.startsWith("questions/") ? path.split("/")[1] : null;
  const questionIndex = questions.findIndex(question => question.id === questionId);
  const question = questions[questionIndex];
  const option = path.startsWith("options/") ? options.find(item => item.id === path.split("/")[1]) : undefined;
  const selected = options.find(item => item.id === demo.selectedId);
  const inspiration = discoveryEvents.find(item => item.id === demo.inspirationId);
  const matchingOptions = options.filter(item => fitsBudget(item, demo.answers.budget));
  const minimumPrice = Math.min(...options.filter(item => item.availability === "AVAILABLE").map(item => item.pricePaise));
  const complete = isComplete(demo.answers);
  const stage = path === "brief" ? 1 : path.startsWith("options") ? 2 : path === "checkout" || path === "booking" ? 3 : 0;

  useEffect(() => {
    setPreview("ready");
    headingRef.current?.focus({ preventScroll: true });
    // Route changes retain the provider's answers, but clear simulated state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path]);

  const back = question ? questionIndex === 0 ? "/" : `/questions/${questions[questionIndex - 1].id}`
    : path === "brief" ? "/questions/transport"
    : option ? "/options"
    : path === "options" ? "/brief"
    : path === "checkout" && selected ? `/options/${selected.id}` : "/";

  let content: ReactNode;
  if (!path) {
    content = <ChatPlanner />;
  } else if (question) {
    content = <ChatPlanner startingQuestion={question.id} />;
  } else if (path === "brief") {
    content = complete ? <div className={s.narrow}><Heading eyebrow="THE BRIEF" title="Here’s the evening you have in mind.">A quick check before we explore the possibilities.</Heading>{demo.chat.idea && <p className={s.demoNotice}>Your original idea: {demo.chat.idea}</p>}{inspiration && <p className={s.demoNotice}>Inspired by <Link href={`/discover/${inspiration.id}`}>{inspiration.title}</Link> from Discover. This sample is not a reserved event.</p>}<div className={s.briefCard}>
      <div><span className={s.briefNumber}>01</span><h2>What</h2><p>{demo.answers.kind} in {demo.answers.where?.toLowerCase()}.</p><dl><dt>When</dt><dd>{demo.answers.when}</dd><dt>Company</dt><dd>{demo.answers.who}</dd></dl></div>
      <div><span className={s.briefNumber}>02</span><h2>Why</h2><p>{demo.answers.occasion}</p></div>
      <div><span className={s.briefNumber}>03</span><h2>Which</h2><dl><dt>Total budget</dt><dd>{formatMoney(demo.answers.budget!)}</dd><dt>Keep in mind</dt><dd>{demo.answers.constraints}</dd><dt>Getting there</dt><dd>{demo.answers.transport}</dd></dl></div>
    </div><div className={s.actions}><Link className={s.secondary} href="/questions/when">Edit answers</Link><Link className={s.primary} href="/options">Explore options <span aria-hidden="true">→</span></Link></div><p className={s.finePrint}>The next screen checks sample totals against your budget. Other requirements are not yet verified.</p></div> : <Empty href="/questions/when" action="Continue in chat">Tell me your preferences in chat to see your brief. Preferences are saved with this conversation in your browser.</Empty>;
  } else if (path === "options") {
    content = complete ? <><Heading eyebrow="A FEW POSSIBILITIES" title="Ideas within your budget.">Available demo samples whose total stays within your budget. Prices are examples, not vendor quotes.</Heading><div className={s.demoNotice}>Your total budget: {formatMoney(demo.answers.budget!)}. Sample prices cover two people. Group size, timing, transport and other requirements have not been verified. These are not live offers.</div><div className={s.optionGrid}>{matchingOptions.map((item, index) => <article key={item.id} className={s.optionCard}><div className={s.cardArt}><Scene kind={item.art} /><span className={s.optionNumber}>0{index + 1}</span></div><div className={s.optionBody}><div className={s.cardMeta}>{item.category} <span>· {item.area}</span></div><h2>{item.title}</h2><Status option={item} /><ul className={s.inclusions}>{item.inclusions.map(inclusion => <li key={inclusion}>{inclusion}</li>)}</ul><div className={s.optionFacts}><span>{item.durationMinutes} min experience</span><span>Travel: {item.travelMinutes === null ? "Not provided" : `${item.travelMinutes} min`}</span></div><p className={s.terms}>{item.cancellationTerms}</p><div className={s.priceRow}><div><strong>{formatMoney(item.pricePaise)}</strong><span>sample total for two · {formatMoney(demo.answers.budget! - item.pricePaise)} below budget</span></div><Link className={s.roundLink} href={`/options/${item.id}`} aria-label={`View ${item.title}`}>↗</Link></div></div></article>)}</div>{matchingOptions.length === 0 && <Empty title={`No sample fits ${formatMoney(demo.answers.budget!)}`} href="/questions/budget" action="Edit budget">Available samples start at {formatMoney(minimumPrice)} for two. We can’t quote a cheaper package without priced inventory. Your budget has not been changed.</Empty>}<Link href="/brief" className={s.textLink}>Not your kind of evening? Edit your brief →</Link></> : <Empty href="/questions/when">Start a conversation to explore the sample options.</Empty>;
  } else if (option) {
    content = complete ? <div className={s.detail}><div><Scene kind={option.art} large /><p className={s.finePrint}>Representative photo · synthetic experience, no real supplier</p></div><div><Heading eyebrow={`${option.category} · ${option.area}`} title={option.title}>{option.description}</Heading><Status option={option} /><p className={s.detailPrice}>{formatMoney(option.pricePaise)} <span>sample total for two</span></p><dl className={s.detailFacts}><dt>Sample start</dt><dd>{formatTime(option.startsAt)} IST</dd><dt>Duration</dt><dd>{option.durationMinutes} minutes</dd><dt>Travel time</dt><dd>{option.travelMinutes === null ? "Not provided" : `${option.travelMinutes} minutes`}</dd></dl><h2 className={s.smallTitle}>A little more included</h2><ul className={s.inclusions}>{option.inclusions.map(item => <li key={item}>{item}</li>)}</ul><div className={s.termsBox}><h3>Cancellation terms</h3><p>{option.cancellationTerms}</p></div><div className={s.actions}><Link className={s.secondary} href="/brief">Customise</Link><button className={s.primary} disabled={!fitsBudget(option, demo.answers.budget)} onClick={() => { if (!fitsBudget(option, demo.answers.budget)) return; demo.select(option.id); router.push("/checkout"); }}>{option.availability === "UNAVAILABLE" ? "Unavailable" : !fitsBudget(option, demo.answers.budget) ? "Over budget" : "Proceed"}{option.availability === "AVAILABLE" && <span aria-hidden="true">→</span>}</button></div><p className={s.finePrint}>Your budget: {formatMoney(demo.answers.budget!)}. Sample only; other needs are unverified. Proceeding does not reserve inventory.</p></div></div> : <Empty href="/questions/when">Complete your brief before choosing a sample experience.</Empty>;
  } else if (path === "checkout") {
    content = selected && complete && fitsBudget(selected, demo.answers.budget) ? <div className={s.narrow}><Heading eyebrow="ONE LAST LOOK" title="Your evening, on the page.">This is a payment simulation. No details or money required.</Heading><div className={s.checkoutCard}><Scene kind={selected.art} /><div><span className={s.eyebrow}>{selected.area}</span><h2>{selected.title}</h2><p>{formatTime(selected.startsAt)} IST · {selected.durationMinutes} min</p></div></div><div className={s.total}><span>Sample total for two</span><strong>{formatMoney(selected.pricePaise)}</strong></div><p className={s.terms}>{selected.cancellationTerms}</p><div className={s.demoNotice}>This sample fits your total budget. Group size, timing and other needs have not been verified. This button only opens a simulated request status.</div><button className={`${s.primary} ${s.fullWidth}`} onClick={() => { if (!fitsBudget(selected, demo.answers.budget)) return; demo.request(); router.push("/booking"); }}>Demo payment <span aria-hidden="true">→</span></button><p className={s.finePrint}>No charge. No payment provider. No reservation.</p></div> : <Empty href={complete ? "/options" : "/questions/when"} action="Choose an experience">Choose an available sample option before opening checkout.</Empty>;
  } else if (path === "booking") {
    content = demo.requested && selected && complete && fitsBudget(selected, demo.answers.budget) ? <div className={s.narrow}><div className={s.pendingIcon} aria-hidden="true">↗</div><Heading eyebrow="YOUR DEMO REQUEST" title="Requested, awaiting vendor confirmation">A little anticipation. Here’s where your request would stand.</Heading><div className={s.requestSummary}><strong>{selected.title}</strong><span>{formatTime(selected.startsAt)} IST</span><span>Payment: simulated only · no money moved</span></div><ol className={s.timeline}>{timeline.map((event, index) => <li key={event.title} className={event.current ? s.currentEvent : ""}><span className={s.timelineDot} aria-hidden="true">{index === 0 ? "✓" : index === 1 ? "·" : ""}</span><div><h2>{event.title}</h2><p>{event.description}</p></div></li>)}</ol><div className={s.demoNotice}>This status will not advance. No real request, vendor contact, or payment was made.</div><button className={s.secondary} onClick={() => { demo.reset(); router.push("/"); }}>Explore another evening <span aria-hidden="true">↗</span></button></div> : <Empty href={complete ? "/options" : "/"}>There’s no demo request in this session. Follow the flow to create one.</Empty>;
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
