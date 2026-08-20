"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { resolveTheme, THEME_CHANGE_EVENT } from "@/lib/theme";

/* Mermaid draws its own colours, so it cannot inherit the page's tokens the way
   CSS does. It has to be told which theme is on screen, and told again when that
   changes — reading `prefers-color-scheme` is not enough, because an explicit
   choice overrides the OS. */

const PALETTE = {
  dark: {
    background: "#151c22",
    primaryColor: "#1a2229",
    primaryTextColor: "#e3e9ed",
    primaryBorderColor: "#2a343c",
    lineColor: "#8b98a4",
    secondaryColor: "#2e1d12",
    tertiaryColor: "#11292b",
  },
  light: {
    background: "#fbfcfc",
    primaryColor: "#f1f4f5",
    primaryTextColor: "#131a20",
    primaryBorderColor: "#cdd5da",
    lineColor: "#64717d",
    secondaryColor: "#f3e3d8",
    tertiaryColor: "#dceaea",
  },
} as const;

/**
 * Renders a Mermaid diagram.
 *
 * Client-side and lazily imported: mermaid is a large dependency and most pages
 * have no diagrams, so it must not sit in the shared bundle. The diagram source
 * is inlined into the lesson body by the content loader, so there is no second
 * network request per diagram.
 */
export function Mermaid({ chart }: { chart: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const reactId = useId();
  const id = `mermaid-${reactId.replace(/[^a-zA-Z0-9]/g, "")}`;

  const [theme, setTheme] = useState<"light" | "dark" | null>(null);

  // Read after mount rather than during render: the server has no document, and
  // guessing here would render one theme's diagram on the other's page.
  useEffect(() => {
    setTheme(resolveTheme());
    const onThemeChange = () => setTheme(resolveTheme());
    window.addEventListener(THEME_CHANGE_EVENT, onThemeChange);
    return () => window.removeEventListener(THEME_CHANGE_EVENT, onThemeChange);
  }, []);

  const draw = useCallback(
    async (resolved: "light" | "dark", cancelled: () => boolean) => {
      try {
        const mermaid = (await import("mermaid")).default;

        mermaid.initialize({
          startOnLoad: false,
          theme: "base",
          securityLevel: "strict",
          fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif",
          themeVariables: { ...PALETTE[resolved] },
        });

        // A fresh id per render: mermaid leaves its own <style> keyed on the id,
        // and reusing one repaints the old palette over the new diagram.
        const { svg } = await mermaid.render(`${id}-${resolved}`, chart);
        if (!cancelled() && containerRef.current) {
          containerRef.current.innerHTML = svg;
        }
      } catch (cause) {
        if (!cancelled()) {
          setError(cause instanceof Error ? cause.message : "Could not render diagram");
        }
      }
    },
    [chart, id],
  );

  useEffect(() => {
    if (theme === null) return;
    let cancelled = false;
    draw(theme, () => cancelled);
    return () => {
      cancelled = true;
    };
  }, [theme, draw]);

  if (error) {
    // Falling back to the source is more useful than an error box — the reader
    // can still follow the structure.
    return (
      <pre className="overflow-x-auto rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface-2)] p-4 font-[family-name:var(--font-mono)] text-xs">
        {chart}
      </pre>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex justify-center overflow-x-auto rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] p-4"
      role="img"
      aria-label="Diagram"
    />
  );
}
