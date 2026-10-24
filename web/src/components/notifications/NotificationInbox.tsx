"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { bookingFixtures, logOfferEvent, matchesOfferInput, offerIsCurrent, offerKey, sampleApplicants, sampleOffer, type InboxItem, type OfferNotice, type TripProfile } from "@/lib/notification-fixtures";
import ConsentCard from "./ConsentCard";
import OfferSettings from "./OfferSettings";
import TripProfileInputs from "./TripProfileInputs";
import OfferCard from "./OfferCard";
import OfferCarousel from "./OfferCarousel";
import OfferDetail from "./OfferDetail";
import Review from "./Review";
import Details from "./Details";
import MockPayment from "./MockPayment";
import Status from "./Status";
import shell from "@/app/shell.module.css";
import s from "./notification.module.css";

type View = "inbox" | "settings" | "detail" | "review" | "details" | "payment" | "status";
type ScreenMode = "ready" | "loading" | "empty" | "error" | "offline";
const titles: Record<View, string> = { inbox: "Notifications", settings: "Offer settings", detail: "Partner offer", review: "Review", details: "Sample details", payment: "Mock payment", status: "Application status" };

function ScreenState({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ScreenMode>("ready");
  const [online, setOnline] = useState(true);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    update(); window.addEventListener("online", update); window.addEventListener("offline", update);
    return () => { window.removeEventListener("online", update); window.removeEventListener("offline", update); };
  }, []);
  const state = online ? mode : "offline";
  return <>
    <label className={s.simulator}>Demo screen state<select value={mode} onChange={event => setMode(event.target.value as ScreenMode)}>
      <option value="ready">Ready</option><option value="loading">Loading</option><option value="empty">Empty</option><option value="error">Error</option><option value="offline">Offline</option>
    </select></label>
    {state !== "ready" && <section className={s.card}>
      <h3>{state === "loading" ? "Loading sample content…" : state === "empty" ? "No sample content here" : state === "offline" ? "You’re offline" : "The sample screen couldn’t load"}</h3>
      <p>{state === "offline" ? "Your in-memory inputs remain here. No application is submitted while offline. Reconnect and retry." : "This is a simulated state. Nothing has been submitted or charged."}</p>
      <button type="button" onClick={() => setMode("ready")}>{state === "loading" ? "Finish demo loading" : state === "empty" ? "Restore sample content" : "Retry"}</button>
    </section>}
    <div hidden={state !== "ready"}>{children}</div>
  </>;
}

export default function NotificationInbox() {
  const [host, setHost] = useState<Element | null>(null);
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<View>("inbox");
  const [items, setItems] = useState<InboxItem[]>([{ ...bookingFixtures[0] }]);
  const [consent, setConsent] = useState(false);
  const [declined, setDeclined] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [profile, setProfile] = useState<TripProfile>({ tripAbroad: "", policyExpiry: "" });
  const [dismissed, setDismissed] = useState<Set<string>>(() => new Set());
  const [submitted, setSubmitted] = useState<Set<string>>(() => new Set());
  const [selected, setSelected] = useState<OfferNotice | null>(null);
  const [applicantId, setApplicantId] = useState("");
  const [flowError, setFlowError] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const bell = useRef<HTMLButtonElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const error = useRef<HTMLParagraphElement>(null);
  const arrivals = useRef(0);
  const submissionLock = useRef(false);
  const keyboardOpen = useRef(false);
  const unread = items.filter(item => !item.read).length;

  // Isolated header insertion: no edits or replacement of AppHeader's children.
  useEffect(() => { setHost(document.querySelector(`.${shell.headerActions}`)); }, []);
  useEffect(() => {
    if (!open) return;
    const node = dialog.current;
    if (!node) return;
    node.showModal();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    heading.current?.focus();
    return () => { node.close(); document.body.style.overflow = previousOverflow; bell.current?.focus(); };
  }, [open]);
  useEffect(() => { if (open) { heading.current?.focus(); if (dialog.current) dialog.current.scrollTop = 0; } }, [view, open]);
  useEffect(() => { if (flowError) error.current?.focus(); }, [flowError]);

  function navigate(next: View) { setFlowError(""); setView(next); }
  function announce(kind: string) { arrivals.current += 1; setAnnouncement(`New ${kind} added. Notification ${arrivals.current}.`); }
  function publishOffer(input: TripProfile, enabled: boolean, stopped: boolean) {
    const allowed = enabled && !stopped && matchesOfferInput(input) && !dismissed.has(offerKey(input)) && offerIsCurrent(sampleOffer);
    const existing = items.find((item): item is OfferNotice => item.type === "offer");
    if (allowed && existing && offerKey(existing.trigger) === offerKey(input)) return;
    setItems(previous => [...previous.filter(item => item.type !== "offer"), ...(allowed ? [{ id: sampleOffer.id, type: "offer" as const, offer: sampleOffer, trigger: { ...input }, read: false }] : [])]);
    if (allowed) announce("partner offer");
  }
  function acceptConsent() { setConsent(true); setDeclined(false); publishOffer(profile, true, blocked); }
  function withdraw() {
    setConsent(false); setDeclined(true); setItems(previous => previous.filter(item => item.type !== "offer"));
    setSelected(null); setApplicantId(""); navigate("settings");
  }
  function dismiss(item: OfferNotice, stop: boolean) {
    logOfferEvent("offer_dismissed");
    if (stop) setBlocked(true);
    else setDismissed(previous => new Set([...previous, offerKey(item.trigger)]));
    setItems(previous => previous.filter(entry => entry.id !== item.id));
    setSelected(null); setApplicantId(""); navigate("inbox");
  }
  function proceed(action: () => void) {
    if (!navigator.onLine) { setFlowError("You’re offline. Reconnect before continuing the mock application."); return; }
    if (!selected || !consent || blocked || !matchesOfferInput(profile) || offerKey(selected.trigger) !== offerKey(profile) || dismissed.has(offerKey(profile))) {
      setFlowError("This sample offer is no longer enabled for your demo inputs. Return to Offer settings."); return;
    }
    if (!offerIsCurrent(selected.offer)) { setFlowError("This sample offer has expired. No mock application was submitted."); return; }
    action();
  }
  const consentCard = !consent && !declined && <ConsentCard onAccept={acceptConsent} onDecline={() => setDeclined(true)} />;

  let content: ReactNode;
  if (view === "inbox") content = <>
    <OfferCarousel />
    <div className={s.actions}><button type="button" disabled={!unread} onClick={() => setItems(previous => previous.map(item => ({ ...item, read: true })))}>Mark all as read</button><button type="button" disabled={items.some(item => item.id === bookingFixtures[1].id)} onClick={() => { setItems(previous => [...previous, { ...bookingFixtures[1] }]); announce("booking update"); }}>Add sample booking update</button></div>
    {blocked && <p>You have stopped travel-cover offers. Booking updates remain available.</p>}
    {!items.length && <p>Your inbox is empty.</p>}
    <div className={s.list}>{items.map(item => item.type === "booking" ? <article className={s.card} key={item.id}><p className={s.label}>Booking update · fixture</p><h3>{item.title}{!item.read && <span className={s.unread}>Unread</span>}</h3><p>{item.message}</p><button type="button" disabled={item.read} onClick={() => setItems(previous => previous.map(entry => entry.id === item.id ? { ...entry, read: true } : entry))}>{item.read ? "Read" : "Mark as read"}</button></article> : <OfferCard key={item.id} item={item} onView={() => {
      logOfferEvent("offer_viewed"); setSelected(item); setApplicantId(""); submissionLock.current = false;
      setItems(previous => previous.map(entry => entry.id === item.id ? { ...entry, read: true } : entry));
      navigate(submitted.has(offerKey(item.trigger)) ? "status" : "detail");
    }} onDismiss={() => dismiss(item, false)} onStop={() => dismiss(item, true)} />)}</div>
  </>;
  else if (view === "settings") content = <>
    <OfferSettings enabled={consent} blocked={blocked} onToggle={() => { if (consent) withdraw(); else setDeclined(false); }} onResume={() => { setBlocked(false); publishOffer(profile, consent, false); }} />
    {consentCard}
    <TripProfileInputs value={profile} onSave={input => { setProfile(input); setSelected(null); setApplicantId(""); publishOffer(input, consent, blocked); }} />
  </>;
  else if (!selected || !consent || blocked) content = <section className={s.card}><h3>No partner offer selected</h3><p>Return to the inbox to view an eligible sample offer.</p><button type="button" onClick={() => navigate("inbox")}>Return to inbox</button></section>;
  else if (view === "detail") content = <OfferDetail offer={selected.offer} onReview={() => proceed(() => { logOfferEvent("offer_purchase_started"); navigate("review"); })} onDecline={() => dismiss(selected, false)} />;
  else if (view === "review") content = <Review offer={selected.offer} onNext={() => proceed(() => navigate("details"))} onCancel={() => { setApplicantId(""); navigate("inbox"); }} />;
  else if (view === "details") content = <Details applicantId={applicantId} onNext={id => proceed(() => { if (sampleApplicants.some(item => item.id === id)) { setApplicantId(id); navigate("payment"); } })} onBack={() => navigate("review")} />;
  else if (view === "payment") content = <MockPayment offer={selected.offer} onBack={() => navigate("details")} onSubmit={() => proceed(() => {
    if (!sampleApplicants.some(item => item.id === applicantId)) { setFlowError("Choose a fictional applicant before using mock payment."); return; }
    if (submissionLock.current || submitted.has(offerKey(selected.trigger))) { navigate("status"); return; }
    submissionLock.current = true;
    setSubmitted(previous => new Set([...previous, offerKey(selected.trigger)])); navigate("status");
  })} />;
  else content = <Status onReturn={() => navigate("inbox")} />;

  return <>
    {host && createPortal(<button type="button" ref={bell} className={s.bell} aria-label={`Notifications, ${unread} unread`} aria-haspopup="dialog" aria-expanded={open} aria-controls="notification-inbox" onClick={event => { keyboardOpen.current = event.detail === 0; setAnnouncement(""); setOpen(true); }}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M6 9a6 6 0 0 1 12 0c0 7 3 7 3 9H3c0-2 3-2 3-9Z"/><path d="M10 21h4"/></svg><span className={s.count} aria-hidden="true">{unread}</span></button>, host)}
    <dialog id="notification-inbox" ref={dialog} className={s.panel} data-keyboard={keyboardOpen.current} aria-labelledby="notification-title" onCancel={event => { event.preventDefault(); setOpen(false); }} onClose={event => { if (!event.currentTarget.open) setOpen(false); }} onKeyDown={event => {
      if (event.key !== "Tab") return;
      const controls = [...event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, a[href], [tabindex="0"]')].filter(node => node.getClientRects().length > 0);
      const first = controls[0], last = controls.at(-1);
      if (!first || !last) { event.preventDefault(); heading.current?.focus(); return; }
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !controls.includes(active as HTMLElement))) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (active === last || !controls.includes(active as HTMLElement))) { event.preventDefault(); first.focus(); }
    }}>
      <div className={s.panelHeader}><h2 id="notification-title" ref={heading} tabIndex={-1}>{titles[view]}</h2><button type="button" aria-label="Close notification inbox" onClick={() => setOpen(false)}>×</button></div>
      <p className={s.banner}>{view === "inbox" ? "Demo: offer artwork only. No purchases or brand partnerships." : "Demo: sample partner, no real policy or payment."}</p>
      <nav className={s.actions} aria-label="Notification inbox"><button type="button" aria-current={view === "inbox" ? "page" : undefined} onClick={() => navigate("inbox")}>Inbox</button><button type="button" aria-current={view === "settings" ? "page" : undefined} onClick={() => navigate("settings")}>Offer settings</button></nav>
      {flowError && <p ref={error} tabIndex={-1} className={s.error}>{flowError}</p>}
      {open && <ScreenState key={view}>{content}</ScreenState>}
      <span className={s.srOnly} aria-live="polite" aria-atomic="true">{announcement}</span>
    </dialog>
  </>;
}
