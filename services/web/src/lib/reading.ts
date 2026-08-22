/**
 * Reading preferences: text size, reading typeface, line height and measure.
 *
 * Same shape as `theme.ts`, and for the same reason — the constants are shared
 * by a server component (the layout's pre-paint script) and a client component
 * (the control), and neither should have to import the other.
 *
 * Every preference is expressed as a data attribute on <html> and consumed by
 * CSS variables in globals.css. No preference is applied by JavaScript at
 * render time, so nothing here can cause a hydration mismatch: the attribute is
 * stamped before first paint and CSS does the rest.
 */

export type TextSize = "s" | "m" | "l" | "xl";
export type ReadingFont = "sans" | "serif" | "mono";
export type LineHeight = "snug" | "normal" | "relaxed";
export type Measure = "narrow" | "normal" | "wide";

export type ReadingPrefs = {
  size: TextSize;
  font: ReadingFont;
  leading: LineHeight;
  measure: Measure;
};

export const READING_STORAGE_KEY = "groundwork-reading";

export const DEFAULT_PREFS: ReadingPrefs = {
  size: "m",
  font: "sans",
  leading: "normal",
  measure: "normal",
};

export const TEXT_SIZE_LABEL: Record<TextSize, string> = {
  s: "Small",
  m: "Medium",
  l: "Large",
  xl: "Larger",
};

export const READING_FONT_LABEL: Record<ReadingFont, string> = {
  sans: "Sans",
  serif: "Serif",
  mono: "Mono",
};

export const LINE_HEIGHT_LABEL: Record<LineHeight, string> = {
  snug: "Snug",
  normal: "Normal",
  relaxed: "Relaxed",
};

export const MEASURE_LABEL: Record<Measure, string> = {
  narrow: "Narrow",
  normal: "Normal",
  wide: "Wide",
};

/** Narrow an unknown stored value without trusting it. */
export function parsePrefs(raw: string | null): ReadingPrefs {
  if (!raw) return DEFAULT_PREFS;
  try {
    const v = JSON.parse(raw) as Partial<ReadingPrefs>;
    return {
      size: v.size && v.size in TEXT_SIZE_LABEL ? v.size : DEFAULT_PREFS.size,
      font: v.font && v.font in READING_FONT_LABEL ? v.font : DEFAULT_PREFS.font,
      leading: v.leading && v.leading in LINE_HEIGHT_LABEL ? v.leading : DEFAULT_PREFS.leading,
      measure: v.measure && v.measure in MEASURE_LABEL ? v.measure : DEFAULT_PREFS.measure,
    };
  } catch {
    return DEFAULT_PREFS;
  }
}

/** Stamp the attributes CSS reads. Used by the control and by the init script. */
export function applyPrefs(prefs: ReadingPrefs): void {
  const root = document.documentElement;
  root.dataset.textSize = prefs.size;
  root.dataset.readingFont = prefs.font;
  root.dataset.leading = prefs.leading;
  root.dataset.measure = prefs.measure;
}

/**
 * The blocking script that runs before first paint.
 *
 * Identical reasoning to the theme script: the preference lives in
 * localStorage, the server cannot read it, and applying it after hydration
 * would reflow the whole page a frame after the reader sees it.
 */
export const readingInitScript = `
(function () {
  try {
    var raw = localStorage.getItem(${JSON.stringify(READING_STORAGE_KEY)});
    if (!raw) return;
    var p = JSON.parse(raw);
    var d = document.documentElement.dataset;
    if (p.size) d.textSize = p.size;
    if (p.font) d.readingFont = p.font;
    if (p.leading) d.leading = p.leading;
    if (p.measure) d.measure = p.measure;
  } catch (e) {}
})();
`;
