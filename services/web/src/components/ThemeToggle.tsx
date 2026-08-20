"use client";

import { useEffect, useState } from "react";
import {
  NEXT_THEME,
  resolveTheme,
  THEME_CHANGE_EVENT,
  THEME_LABEL,
  THEME_STORAGE_KEY,
  type ThemeChoice,
} from "@/lib/theme";

function announce() {
  window.dispatchEvent(
    new CustomEvent(THEME_CHANGE_EVENT, { detail: { resolved: resolveTheme() } }),
  );
}

/**
 * Three-state theme control: system, light, dark.
 *
 * "System" is kept as a distinct state rather than being resolved to one of the
 * other two at first click, because it is the only one that keeps tracking the
 * reader's OS — which matters for anyone whose machine switches at sunset.
 */
export function ThemeToggle() {
  const [choice, setChoice] = useState<ThemeChoice>("system");
  // Rendered only after mount. The server cannot know the stored preference, so
  // rendering the label during SSR would guarantee a hydration mismatch.
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(THEME_STORAGE_KEY);
    } catch {
      // Storage is denied outright in some privacy modes. The toggle still
      // works for the session; it just does not persist.
    }
    if (stored === "light" || stored === "dark" || stored === "system") {
      setChoice(stored);
    }
    setReady(true);
  }, []);

  // While on "system", an OS change has to reach the diagrams too. The CSS
  // follows the media query by itself; Mermaid has to be told.
  useEffect(() => {
    if (choice !== "system") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", announce);
    return () => media.removeEventListener("change", announce);
  }, [choice]);

  function cycle() {
    const next = NEXT_THEME[choice];
    setChoice(next);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Not persisting is survivable; not switching would not be.
    }
    const root = document.documentElement;
    if (next === "system") {
      delete root.dataset.theme;
    } else {
      root.dataset.theme = next;
    }
    announce();
  }

  return (
    <button
      type="button"
      onClick={cycle}
      // The label is deliberately blank on the server and filled after mount,
      // because only the client knows which theme was chosen.
      suppressHydrationWarning
      aria-label={`Colour theme: ${THEME_LABEL[choice].toLowerCase()}. Activate to change.`}
      title={`Theme: ${THEME_LABEL[choice]}`}
      className="min-w-[3.6rem] rounded-sm border border-[var(--color-rule)] px-2 py-1 font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] text-[var(--color-muted)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
    >
      {ready ? THEME_LABEL[choice] : " "}
    </button>
  );
}
