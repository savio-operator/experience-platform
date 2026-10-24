"use client";

import s from "./notification.module.css";

export default function Status({ onReturn }: { onReturn: () => void }) {
  return <section><p className={s.label}>Step 4 of 4 · Status</p><h3>Application submitted, awaiting insurer.</h3><p>Simulated status only. Nothing was sent to an insurer, no money moved, and no policy or insurance cover exists.</p><p>This demo does not advance to an issued-policy state.</p><button type="button" onClick={onReturn}>Return to inbox</button></section>;
}
