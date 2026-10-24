"use client";

import { useState } from "react";
import s from "./notification.module.css";

export default function ConsentCard({ onAccept, onDecline }: { onAccept: () => void; onDecline: () => void }) {
  const [checked, setChecked] = useState(false);
  return <section className={s.card} aria-labelledby="offer-consent-title">
    <h3 id="offer-consent-title">Would you like sample partner offers?</h3>
    <p>Optional. This demo uses only the trip choice and policy-expiry date you enter here to show clearly labelled fictional offers. Nothing is sent to a partner.</p>
    <p>You can withdraw in Offer settings. Booking updates stay available either way.</p>
    <label className={s.check}><input type="checkbox" checked={checked} onChange={event => setChecked(event.target.checked)} />I want to see sample partner offers based on these demo inputs.</label>
    <div className={s.actions}><button type="button" className={s.primary} disabled={!checked} onClick={onAccept}>Enable sample offers</button><button type="button" onClick={onDecline}>No thanks</button></div>
  </section>;
}
