"use client";

import { useRef, useState } from "react";
import { showcaseOffers } from "@/lib/notification-fixtures";
import Image from "next/image";
import s from "./notification.module.css";

export default function OfferCarousel() {
  const track = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);
  const [gift, setGift] = useState<string | null>(null);
  function go(index: number) {
    const node = track.current;
    const card = node?.children[index] as HTMLElement | undefined;
    if (!node || !card) return;
    node.scrollTo({ left: card.offsetLeft, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }
  return <section className={s.carousel} aria-label="Brand offer artwork" aria-roledescription="carousel">
    <div ref={track} className={s.carouselTrack} tabIndex={0} aria-label="Offers: swipe or use left and right arrow keys" onKeyDown={event => {
      if (event.key === "ArrowRight") { event.preventDefault(); go(Math.min(active + 1, showcaseOffers.length - 1)); }
      if (event.key === "ArrowLeft") { event.preventDefault(); go(Math.max(active - 1, 0)); }
    }} onScroll={() => {
      const node = track.current;
      if (!node) return;
      const cards = Array.from(node.children) as HTMLElement[];
      const nearest = cards.reduce((best, card, index) => Math.abs(card.offsetLeft - node.scrollLeft) < Math.abs(cards[best].offsetLeft - node.scrollLeft) ? index : best, 0);
      setActive(nearest);
    }}>
      {showcaseOffers.map((offer, index) => <article key={offer.id} className={s.offerSlide} role="group" aria-roledescription="slide" aria-label={`${index + 1} of ${showcaseOffers.length}: ${offer.title}`}>
        <Image className={s.offerArtwork} src={offer.image} width={1080} height={1920} sizes="(max-width: 700px) 80vw, 320px" alt={`${offer.brand}: ${offer.title}. Reference promotional artwork; current eligibility unverified.`} />
        <div className={s.offerCaption}>
          <h3>{offer.brand}</h3>
          <p>{offer.title}</p>
          <button className={`${s.primary} ${s.claimButton}`} type="button" aria-label={`Claim ${offer.brand} demo gift`} aria-expanded={gift === offer.id} aria-controls={`gift-${offer.id}`} onClick={() => setGift(gift === offer.id ? null : offer.id)}>Claim</button>
          <p className={s.muted}>Demo gift only · not redeemable</p>
          {gift === offer.id && <section id={`gift-${offer.id}`} className={s.giftCard} aria-label={`${offer.brand} demo gift`}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M4 11v10h16V11M3 7h18v4H3zM12 7v14M12 7H8a3 3 0 1 1 3-3l1 3Zm0 0h4a3 3 0 1 0-3-3l-1 3Z" /></svg>
            <p className={s.label}>A little gift inspiration</p>
            <h3>Your {offer.brand} demo gift</h3>
            <p>{offer.title}</p>
            <p className={s.muted}>This is a preview, not a voucher. No gift, discount or reward has been issued by {offer.brand}.</p>
            <p className={s.muted}>{offer.note}</p>
            <p className={s.muted}>Artwork source: {offer.source}. No affiliation or endorsement implied.</p>
          </section>}
        </div>
      </article>)}
    </div>
    <div className={s.carouselControls}>
      <button type="button" aria-label="Previous offer" disabled={active === 0} onClick={() => go(active - 1)}>←</button>
      <span aria-label={`Offer ${active + 1} of ${showcaseOffers.length}`}>{active + 1} / {showcaseOffers.length}</span>
      <button type="button" aria-label="Next offer" disabled={active === showcaseOffers.length - 1} onClick={() => go(active + 1)}>→</button>
    </div>
  </section>;
}
