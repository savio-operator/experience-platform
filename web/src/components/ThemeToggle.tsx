"use client";

import { useEffect, useState } from "react";
import s from "@/app/shell.module.css";

export default function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const sync = () => {
      let saved: string | null = null;
      try { saved = localStorage.getItem("elsewhere-theme"); } catch { /* Storage is optional. */ }
      const next = saved === "dark" || (saved !== "light" && media.matches);
      document.documentElement.dataset.theme = next ? "dark" : "light";
      setDark(next);
    };
    sync();
    media.addEventListener("change", sync);
    window.addEventListener("storage", sync);
    return () => { media.removeEventListener("change", sync); window.removeEventListener("storage", sync); };
  }, []);

  return <button className={s.themeToggle} type="button" aria-label="Dark mode" aria-pressed={dark}
    title={dark ? "Switch to light mode" : "Switch to dark mode"} onClick={() => {
      const next = !dark;
      setDark(next);
      document.documentElement.dataset.theme = next ? "dark" : "light";
      try { localStorage.setItem("elsewhere-theme", next ? "dark" : "light"); } catch { /* Keep the current session usable. */ }
    }}><span aria-hidden="true">{dark ? "☀" : "☾"}</span><span>{dark ? "Light" : "Dark"}</span></button>;
}
