"use client";

import type { PartnerOffer } from "@/lib/notification-fixtures";
import { formatMoney } from "@/lib/fixtures";
import s from "./notification.module.css";

export default function Review({ offer, onNext, onCancel }: { offer: PartnerOffer; onNext: () => void; onCancel: () => void }) {
  return <section><p className={s.label}>Step 1 of 4 · Review</p><h3>Review the sample application</h3><p>Partner offer · {offer.partner}</p><p>{offer.plan}</p><dl className={s.facts}><dt>Illustrative premium</dt><dd>{formatMoney(offer.premiumPaise)}</dd><dt>Amount charged in this demo</dt><dd>{formatMoney(0)}</dd></dl><p>No cover begins in this demo. The following screens use fictional applicant details and a simulated payment.</p><div className={s.notice}>Legal disclosure supplied by licensed partner</div><div className={s.actions}><button type="button" className={s.primary} onClick={onNext}>Continue to sample details</button><button type="button" onClick={onCancel}>Cancel application</button></div></section>;
}
