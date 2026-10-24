"use client";

import { offerIsCurrent, type PartnerOffer } from "@/lib/notification-fixtures";
import { formatMoney } from "@/lib/fixtures";
import s from "./notification.module.css";

export default function OfferDetail({ offer, onReview, onDecline }: { offer: PartnerOffer; onReview: () => void; onDecline: () => void }) {
  const current = offerIsCurrent(offer);
  return <section>
    <p className={s.label}>Partner offer · {offer.partner}</p><h3>{offer.plan}</h3>
    <p>All amounts and dates are illustrative fixtures, not a quote or real insurance terms.</p>
    <dl className={s.facts}><dt>Insurer</dt><dd>{offer.partner} · fictional</dd><dt>Plan name</dt><dd>{offer.plan}</dd><dt>Sample cover</dt><dd>{formatMoney(offer.coverPaise)}</dd><dt>Sample premium</dt><dd>{formatMoney(offer.premiumPaise)}</dd><dt>Inclusions</dt><dd>{offer.inclusions.join(" ")}</dd><dt>Exclusions</dt><dd>{offer.exclusions.join(" ")}</dd><dt>Waiting periods</dt><dd>{offer.waitingPeriods}</dd><dt>Validity</dt><dd>{offer.validity}</dd><dt>Free-look / cancellation terms</dt><dd>{offer.cancellation}</dd><dt>Sample offer expiry</dt><dd>{new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" }).format(new Date(offer.expiresAt))} IST</dd></dl>
    <div className={s.notice}>Legal disclosure supplied by licensed partner</div>
    {!current && <p>This sample offer has expired. A mock application cannot be started.</p>}
    <div className={s.actions}><button type="button" className={s.primary} disabled={!current} onClick={onReview}>Review sample application</button><button type="button" onClick={onDecline}>Not interested</button></div>
  </section>;
}
