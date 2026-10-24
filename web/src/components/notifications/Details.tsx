"use client";

import { useState } from "react";
import { sampleApplicants } from "@/lib/notification-fixtures";
import s from "./notification.module.css";

export default function Details({ applicantId, onNext, onBack }: { applicantId: string; onNext: (id: string) => void; onBack: () => void }) {
  const [id, setId] = useState(applicantId);
  const [error, setError] = useState("");
  const applicant = sampleApplicants.find(item => item.id === id);
  return <form onSubmit={event => { event.preventDefault(); if (!applicant) { setError("Choose a fictional applicant to continue."); return; } onNext(applicant.id); }}>
    <p className={s.label}>Step 2 of 4 · Details</p><h3>Use fictional applicant details</h3><p>Do not enter real personal, health or identity information. Only the two sample records below can be used.</p>
    <label className={s.field}>Sample applicant<select value={id} aria-invalid={Boolean(error)} aria-describedby="applicant-error" onChange={event => { setId(event.target.value); setError(""); }}><option value="">Choose a sample</option>{sampleApplicants.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    {applicant && <dl className={s.facts}><dt>Fictional name</dt><dd>{applicant.name}</dd><dt>Non-deliverable sample email</dt><dd>{applicant.email}</dd></dl>}
    <p id="applicant-error" className={s.error}>{error}</p><div className={s.actions}><button type="submit" className={s.primary}>Continue to mock payment</button><button type="button" onClick={onBack}>Back to review</button></div>
  </form>;
}
