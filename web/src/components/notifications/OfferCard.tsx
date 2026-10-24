"use client";

import type { OfferNotice } from "@/lib/notification-fixtures";
import { formatMoney } from "@/lib/fixtures";
import s from "./notification.module.css";

export default function OfferCard({ item, onView, onDismiss, onStop }: { item: OfferNotice; onView: () => void; onDismiss: () => void; onStop: () => void }) {
  return <article className={s.card}>
    <p className={s.label}>Partner offer · {item.offer.partner}</p>
    <h3>{item.offer.plan}{!item.read && <span className={s.unread}>Unread</span>}</h3>
    <p>Fictional partner and product. Sample premium {formatMoney(item.offer.premiumPaise)}.</p>
    <details className={s.reason}><summary>Why you’re seeing this</summary><p>You entered these values in the demo brief/profile and enabled sample offers:</p><dl><dt>Trip choice</dt><dd>{item.trigger.tripAbroad}</dd><dt>Policy-expiry date</dt><dd className={s.exact}>{item.trigger.policyExpiry}</dd></dl><p>No other inputs or inferred interests were used.</p></details>
    <div className={s.actions}><button type="button" onClick={onView}>View</button><button type="button" onClick={onDismiss}>Not interested</button><button type="button" onClick={onStop}>Stop showing offers like this</button></div>
  </article>;
}
