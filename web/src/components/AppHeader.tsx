"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import s from "@/app/shell.module.css";

export default function AppHeader() {
  const discovery = usePathname().startsWith("/discover");
  return <header className={s.header}>
    <Link href="/" className={s.brand} aria-label="Elsewhere home"><span className={s.mark}>e.</span>elsewhere</Link>
    <nav className={s.modeSwitch} aria-label="App mode">
      <Link href="/" aria-current={!discovery ? "page" : undefined}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M20 11.5a8 8 0 0 1-8 8H4v-8a8 8 0 0 1 16 0Z"/><path d="M8 10h8M8 14h5"/></svg>Chat
      </Link>
      <Link href="/discover" aria-current={discovery ? "page" : undefined}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m16 8-2.5 5.5L8 16l2.5-5.5L16 8Z"/></svg>Discover
      </Link>
    </nav>
    <span className={s.location}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2.5"/></svg>Kochi, Kerala</span>
  </header>;
}
