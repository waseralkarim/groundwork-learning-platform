"use client";

import { useEffect, useRef, useState } from "react";
import {
  applyPrefs,
  DEFAULT_PREFS,
  LINE_HEIGHT_LABEL,
  MEASURE_LABEL,
  type ReadingPrefs as Prefs,
  parsePrefs,
  READING_FONT_LABEL,
  READING_STORAGE_KEY,
  TEXT_SIZE_LABEL,
} from "@/lib/reading";

/**
 * Reading controls: text size, typeface, line height and measure.
 *
 * A platform whose core activity is reading technical prose for ninety minutes
 * should let the reader set the things that make that bearable. All four are
 * plain CSS variables, so nothing here re-renders the page — the attribute
 * changes and the browser reflows.
 */
export function ReadingPrefs() {
  const [open, setOpen] = useState(false);
  const [prefs, setPrefs] = useState<Prefs>(DEFAULT_PREFS);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let raw: string | null = null;
    try {
      raw = localStorage.getItem(READING_STORAGE_KEY);
    } catch {
      // Storage denied. The controls still work for this session.
    }
    setPrefs(parsePrefs(raw));
  }, []);

  // Close on outside click and on Escape — both expected of a popover, and
  // neither provided for free.
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    function onClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  function update(patch: Partial<Prefs>) {
    const next = { ...prefs, ...patch };
    setPrefs(next);
    applyPrefs(next);
    try {
      localStorage.setItem(READING_STORAGE_KEY, JSON.stringify(next));
    } catch {
      // Not persisting is survivable; not applying would not be.
    }
  }

  function reset() {
    setPrefs(DEFAULT_PREFS);
    applyPrefs(DEFAULT_PREFS);
    try {
      localStorage.removeItem(READING_STORAGE_KEY);
    } catch {
      // As above.
    }
  }

  return (
    <div ref={panelRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="dialog"
        title="Reading preferences"
        className="rounded-sm border border-[var(--color-rule)] px-2 py-1 font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] text-[var(--color-muted)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
      >
        Aa
      </button>

      {open ? (
        <div
          // biome-ignore lint/a11y/useSemanticElements: a <dialog> would trap
          // focus and dim the page; this is a lightweight preferences popover.
          role="dialog"
          aria-label="Reading preferences"
          className="absolute right-0 z-50 mt-2 w-[17rem] rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-4 shadow-xl shadow-black/10"
        >
          <div className="flex items-baseline justify-between">
            <h2 className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.14em] text-[var(--color-muted)]">
              Reading
            </h2>
            <button
              type="button"
              onClick={reset}
              className="font-[family-name:var(--font-mono)] text-[0.58rem] uppercase tracking-[0.12em] text-[var(--color-muted)] hover:text-[var(--color-accent)]"
            >
              Reset
            </button>
          </div>

          <Group
            label="Text size"
            options={TEXT_SIZE_LABEL}
            value={prefs.size}
            onChange={(size) => update({ size })}
          />
          <Group
            label="Typeface"
            options={READING_FONT_LABEL}
            value={prefs.font}
            onChange={(font) => update({ font })}
          />
          <Group
            label="Line height"
            options={LINE_HEIGHT_LABEL}
            value={prefs.leading}
            onChange={(leading) => update({ leading })}
          />
          <Group
            label="Measure"
            options={MEASURE_LABEL}
            value={prefs.measure}
            onChange={(measure) => update({ measure })}
          />

          <p className="mt-4 border-t border-[var(--color-rule-soft)] pt-3 text-[0.68rem] leading-relaxed text-[var(--color-muted)]">
            Saved in this browser. Measure sets how wide a line of prose runs before it wraps.
          </p>
        </div>
      ) : null}
    </div>
  );
}

function Group<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: Record<T, string>;
  value: T;
  onChange: (v: T) => void;
}) {
  const entries = Object.entries(options) as Array<[T, string]>;
  return (
    <fieldset className="mt-4">
      <legend className="font-[family-name:var(--font-mono)] text-[0.58rem] uppercase tracking-[0.13em] text-[var(--color-muted)]">
        {label}
      </legend>
      <div className="mt-1.5 flex gap-1">
        {entries.map(([key, text]) => (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            aria-pressed={value === key}
            className={`flex-1 rounded border px-1.5 py-1.5 text-[0.66rem] transition-colors ${
              value === key
                ? "border-[var(--color-accent)] bg-[var(--color-accent)] text-[var(--color-surface)]"
                : "border-[var(--color-rule)] text-[var(--color-ink-soft)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
            }`}
          >
            {text}
          </button>
        ))}
      </div>
    </fieldset>
  );
}
