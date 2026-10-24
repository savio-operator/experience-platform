"use client";

import { useState } from "react";
import { validExpiry, type TripProfile } from "@/lib/notification-fixtures";
import s from "./notification.module.css";

export default function TripProfileInputs({ value, onSave }: { value: TripProfile; onSave: (value: TripProfile) => void }) {
  const [draft, setDraft] = useState(value);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  return <form className={s.card} onSubmit={event => {
    event.preventDefault();
    if (draft.policyExpiry && !validExpiry(draft.policyExpiry)) { setError("Enter a valid date as YYYY-MM-DD, or leave it blank."); setSaved(false); return; }
    onSave({ ...draft }); setError(""); setSaved(true);
  }}>
    <h3>Demo brief and profile</h3>
    <p>Use sample inputs. These fields are separate from your Kochi plan. Trips are outside the pilot scope.</p>
    <label className={s.field}>Trip choice<select value={draft.tripAbroad} onChange={event => { setDraft({ ...draft, tripAbroad: event.target.value }); setSaved(false); }}>
      <option value="">Not provided</option><option value="Trip abroad">Trip abroad</option><option value="No trip abroad">No trip abroad</option>
    </select></label>
    <label className={s.field}>Policy-expiry date you enter<input type="text" autoComplete="off" spellCheck={false} placeholder="YYYY-MM-DD" maxLength={10} value={draft.policyExpiry} aria-invalid={Boolean(error)} aria-describedby="profile-date-help profile-date-error" onChange={event => { setDraft({ ...draft, policyExpiry: event.target.value }); setError(""); setSaved(false); }} /></label>
    <p id="profile-date-help" className={s.muted}>A sample offer matches only when you explicitly choose “Trip abroad” and enter a valid date. No assumptions about expiry timing or insurance needs are made.</p>
    <p id="profile-date-error" className={s.error}>{error}</p>
    <button type="submit">Save demo inputs</button>
    {saved && <p>Demo inputs saved for this session.</p>}
  </form>;
}
