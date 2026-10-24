import type { Metadata } from "next";
import Link from "next/link";
import { DemoProvider } from "@/components/DemoProvider";
import "./globals.css";
import styles from "./shell.module.css";

export const metadata: Metadata = { title: "Elsewhere · A little more Kochi", description: "A fixture-only experience planning demo. No real booking or payment." };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>
    <div className={styles.banner}>Demo. No real booking or payment.</div>
    <a className="skip" href="#main">Skip to content</a>
    <header className={styles.header}>
      <Link href="/" className={styles.brand} aria-label="Elsewhere home"><span className={styles.mark}>e.</span>elsewhere</Link>
      <span className={styles.location}><span aria-hidden="true">◉</span> KOCHI, KERALA</span>
    </header>
    <DemoProvider>{children}</DemoProvider>
    <footer className={styles.footer}><span>A little less scrolling. A little more living.</span><span>Made for a good day in Kochi <span aria-hidden="true">↗</span></span></footer>
  </body></html>;
}
