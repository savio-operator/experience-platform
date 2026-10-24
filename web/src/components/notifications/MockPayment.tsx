"use client";

import type { PartnerOffer } from "@/lib/notification-fixtures";
import { formatMoney } from "@/lib/fixtures";
import s from "./notification.module.css";

export default function MockPayment({ offer, onSubmit, onBack }: { offer: PartnerOffer; onSubmit: () => void; onBack: () => void }) {
  return <section><p className={s.label}>Step 3 of 4 · Mock payment</p><h3>Simulate a payment</h3><dl className={s.facts}><dt>Illustrative premium</dt><dd>{formatMoney(offer.premiumPaise)}</dd><dt>Actual charge</dt><dd>{formatMoney(0)}</dd></dl><p>No card details, UPI, bank account or money are used. This action changes only the in-memory demo status.</p><div className={s.actions}><button type="button" className={s.primary} onClick={onSubmit}>Simulate payment and submit</button><button type="button" onClick={onBack}>Back to details</button></div></section>;
}
