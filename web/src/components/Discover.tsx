"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useDemo } from "./DemoProvider";
import Photo from "./Photo";
import { discoveryEvents, formatTime, photos } from "@/lib/fixtures";
import s from "./discover.module.css";

const categories = ["All", "Outdoors", "Live music", "Workshops", "Food", "Art", "Wellness"];
const areas = ["All Kochi", "Fort Kochi", "Panampilly Nagar", "Marine Drive", "Kakkanad", "Edappally"];
type Preview = "ready" | "loading" | "empty" | "error";

export default function Discover({ eventId }: { eventId?: string }) {
  const demo = useDemo();
  const router = useRouter();
  const [preview, setPreview] = useState<Preview>("ready");
  const { category, area, query } = demo.discovery;
  const event = discoveryEvents.find(item => item.id === eventId);
  const filtered = discoveryEvents.filter(item =>
    (category === "All" || item.category === category) &&
    (area === "All Kochi" || item.area === area) &&
    `${item.title} ${item.area} ${item.category} ${item.description}`.toLowerCase().includes(query.trim().toLowerCase()),
  );

  function bringToChat() {
    if (!event) return;
    demo.setInspirationId(event.id);
    if (!demo.chat.messages.length && !demo.chat.draft.trim()) {
      demo.setChat(previous => ({ ...previous, draft: `I’d like to plan something like “${event.title}” in Kochi.` }));
    }
    router.push("/");
  }

  return <main id="main" className={s.main}>
    <div className={s.utility}>
      {eventId ? <Link href="/discover" className={s.back}>← Back to Discover</Link> : <span>YOUR CITY, A LITTLE CLOSER</span>}
      <label className={s.preview}>Preview state<select value={preview} onChange={e => setPreview(e.target.value as Preview)}><option value="ready">Ready</option><option value="loading">Loading</option><option value="empty">Empty</option><option value="error">Error</option></select></label>
    </div>
    {preview !== "ready" ? <section className={s.state} role={preview === "error" ? "alert" : "status"}>
      <p className={s.kicker}>DISCOVER KOCHI</p>
      <h1>{preview === "loading" ? "Finding a little inspiration…" : preview === "empty" ? "A quiet moment in the city." : "We couldn’t load the city."}</h1>
      <p>{preview === "loading" ? "Simulated loading. Your conversation and filters are still here." : preview === "empty" ? "There are no event listings in this simulated state." : "Simulated error. Your conversation and filters haven’t changed."}</p>
      <button className={s.primary} onClick={() => setPreview("ready")}>{preview === "error" ? "Try again" : "Restore demo listings"} →</button>
    </section> : eventId ? event ? <>
      <div className={s.detailGrid}>
        <div><div className={s.detailPhoto}><Photo id={event.photo} eager /><span className={s.imageLabel}>Representative photo</span></div><a className={s.credit} href={photos[event.photo].source} target="_blank" rel="noreferrer">Photo: {photos[event.photo].credit} ↗</a></div>
        <section className={s.detailCopy}>
          <p className={s.kicker}>{event.category} · {event.area}</p>
          <h1>{event.title}</h1><p className={s.description}>{event.description}</p>
          <dl className={s.facts}><div><dt>Sample time</dt><dd>{formatTime(event.startsAt)} IST</dd></div><div><dt>Sample duration</dt><dd>{event.duration}</dd></div><div><dt>Area</dt><dd>{event.area}, Kochi</dd></div><div><dt>Price & availability</dt><dd>Not verified</dd></div></dl>
          <p className={s.notice}><strong>Demo event concept.</strong> This is not a live or bookable listing. {event.note}</p>
          <button className={s.primary} onClick={bringToChat}>Bring this idea into Chat <span aria-hidden="true">↗</span></button>
          <p className={s.hint}>Your conversation stays intact. Nothing is sent or booked automatically.</p>
        </section>
      </div>
    </> : <section className={s.state}><h1>This idea isn’t here.</h1><p>Return to Discover to explore the sample collection.</p><Link className={s.primary} href="/discover">Explore Kochi →</Link></section> : <>
      <section className={s.hero}>
        <Photo id="water" sizes="(max-width: 1200px) 100vw, 1144px" eager />
        <div className={s.heroShade} />
        <div className={s.heroContent}><span className={s.heroLabel}>THE KOCHI EDIT</span><h1>A good day is<br />closer than you think.</h1><p>Live music, little adventures, and things worth<br className={s.desktopBreak} /> putting your phone away for.</p><a href="#city-listings" className={s.heroButton}>Find your kind of plan <span aria-hidden="true">↓</span></a></div>
        <span className={s.heroLocation}>FORT KOCHI, KERALA <span aria-hidden="true">↗</span></span>
      </section>
      <div className={s.introduction} id="city-listings"><div><p className={s.kicker}>STEP OUT. TUNE IN.</p><h2>Find your kind of Kochi.</h2></div><p>A starting point for your next plan.<br />See something you like? Take it to Chat.</p></div>
      <p className={s.demoNote}><span>DEMO COLLECTION</span>Sample events for 24–25 October 2026. Schedules and availability are unverified; photos are representative.</p>
      <div className={s.filters}>
        <div className={s.search}><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg><label className={s.srOnly} htmlFor="discover-search">Search events and experiences</label><input id="discover-search" type="search" placeholder="A mood, an activity, a neighbourhood…" value={query} onChange={e => demo.setDiscovery(previous => ({ ...previous, query: e.target.value }))} /></div>
        <label className={s.area}><span className={s.srOnly}>Kochi area</span><select aria-label="Kochi area" value={area} onChange={e => demo.setDiscovery(previous => ({ ...previous, area: e.target.value }))}>{areas.map(item => <option key={item}>{item}</option>)}</select></label>
      </div>
      <div className={s.categories} aria-label="Event categories">{categories.map(item => <button key={item} aria-pressed={category === item} onClick={() => demo.setDiscovery(previous => ({ ...previous, category: item }))}>{item === "All" ? "All experiences" : item}</button>)}</div>
      <div className={s.results}><span role="status" aria-live="polite">{filtered.length} {filtered.length === 1 ? "idea" : "ideas"} to get you out there</span><span>Kochi, with a little curiosity</span></div>
      {filtered.length ? <div className={s.grid}>{filtered.map(item => <article className={s.card} key={item.id}>
        <Link href={`/discover/${item.id}`} className={s.cardLink}>
          <div className={s.cardPhoto}><Photo id={item.photo} sizes="(max-width: 600px) 100vw, (max-width: 950px) 50vw, 33vw" /><span className={s.cardTag}>{item.category}</span><span className={s.cardArrow} aria-hidden="true">↗</span></div>
          <div className={s.cardBody}><p className={s.cardTime}>{formatTime(item.startsAt)} IST <span>· Sample</span></p><h3>{item.title}</h3><p className={s.cardArea}>{item.area} <span>· {item.duration}</span></p></div>
        </Link>
      </article>)}</div> : <section className={s.state}><h2>No plans in this corner yet.</h2><p>Try a different area, category, or search. These are sample listings, so the collection is small.</p><button className={s.primary} onClick={() => demo.setDiscovery({ category: "All", area: "All Kochi", query: "" })}>Clear filters →</button></section>}
      <section className={s.chatInvite}><span className={s.chatMark} aria-hidden="true">e.</span><div><h2>More of a “you decide” person?</h2><p>Tell Chat your mood. We’ll take it one question at a time.</p></div><Link className={s.primary} href="/">Let’s make a plan <span aria-hidden="true">↗</span></Link></section>
    </>}
  </main>;
}
