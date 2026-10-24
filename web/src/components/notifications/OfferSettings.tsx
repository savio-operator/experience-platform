"use client";

import s from "./notification.module.css";

export default function OfferSettings({ enabled, blocked, onToggle, onResume }: { enabled: boolean; blocked: boolean; onToggle: () => void; onResume: () => void }) {
  return <section className={s.card} aria-labelledby="offer-settings-title">
    <h3 id="offer-settings-title">Offer settings</h3>
    <label className={s.check}><input type="checkbox" role="switch" checked={enabled} onChange={onToggle} />Show sample partner offers</label>
    <p>{enabled ? "Turning this off withdraws consent, removes partner offers and closes any unfinished mock purchase. Booking updates are unaffected." : "Offers are off. Turning this on opens the consent card; it does not enable offers automatically."}</p>
    {enabled && <button type="button" onClick={onToggle}>Withdraw offer consent</button>}
    {blocked && <div><p>Travel-cover offers are stopped for this session.</p><button type="button" disabled={!enabled} onClick={onResume}>Allow travel-cover offers again</button></div>}
    <p className={s.muted}>Settings and inputs are kept in memory only and reset on refresh.</p>
  </section>;
}
