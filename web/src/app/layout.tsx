import type { Metadata, Viewport } from "next";
import { DemoProvider } from "@/components/DemoProvider";
import AppHeader from "@/components/AppHeader";
import { photos } from "@/lib/fixtures";
import "./globals.css";
import styles from "./shell.module.css";

export const metadata: Metadata = { title: "Elsewhere · A little more Kochi", description: "A fixture-only experience planning demo. No real booking or payment." };

export const viewport: Viewport = {
  width: "device-width", initialScale: 1, viewportFit: "cover",
  interactiveWidget: "resizes-content", themeColor: "#f8f7f2",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>
    <div className={styles.banner}>Demo. No real booking or payment.</div>
    <a className="skip" href="#main">Skip to content</a>
    <AppHeader />
    <DemoProvider>{children}</DemoProvider>
    <footer className={styles.footer}><span>A little less scrolling. A little more living.</span><details className={styles.credits}><summary>Photography credits</summary><p>Representative photography. Activity photos do not depict the listed demo events.</p>{Object.entries(photos).map(([id, photo]) => <a key={id} href={photo.source} target="_blank" rel="noreferrer">{photo.credit} · {photo.subject} ↗</a>)}</details><span>Made for a good day in Kochi <span aria-hidden="true">↗</span></span></footer>
  </body></html>;
}
