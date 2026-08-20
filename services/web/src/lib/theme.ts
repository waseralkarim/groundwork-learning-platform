/**
 * Theme constants and resolution, shared by a server component (the layout's
 * pre-paint script), a client component (the toggle) and a lazily-imported
 * client component (Mermaid).
 *
 * It lives here rather than in the toggle so that none of those three has to
 * pull in the others: a server component importing from a `"use client"` module
 * works, but it drags the whole component into the graph for the sake of a
 * string constant.
 */

export type ThemeChoice = "system" | "light" | "dark";

export const THEME_STORAGE_KEY = "groundwork-theme";

/** Fired on `window` whenever the effective theme changes, so components that
 *  draw their own colours — Mermaid — can redraw. CSS needs no such help. */
export const THEME_CHANGE_EVENT = "groundwork:themechange";

/** system → light → dark → system. A map rather than index arithmetic, so the
 *  cycle is total and the compiler can see that it is. */
export const NEXT_THEME: Record<ThemeChoice, ThemeChoice> = {
  system: "light",
  light: "dark",
  dark: "system",
};

export const THEME_LABEL: Record<ThemeChoice, string> = {
  system: "System",
  light: "Light",
  dark: "Dark",
};

/**
 * What is actually on screen right now.
 *
 * `system` is a real third state rather than a synonym for one of the other
 * two: it stamps no attribute, so `prefers-color-scheme` decides, and it keeps
 * deciding if the reader's OS switches at sunset while the page is open.
 */
export function resolveTheme(): "light" | "dark" {
  const stamped = document.documentElement.dataset.theme;
  if (stamped === "light" || stamped === "dark") return stamped;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/**
 * Palettes for the things that paint themselves.
 *
 * CSS variables reach anything styled with CSS. A terminal emulator drawing to
 * a canvas and a diagram renderer generating SVG both need the values handed to
 * them as JavaScript, and both need handing them again when the theme changes.
 */
export const TERMINAL_THEME = {
  dark: { background: "#0e1317", foreground: "#e3e9ed", cursor: "#e08447" },
  light: { background: "#f1f4f5", foreground: "#131a20", cursor: "#a24c18" },
} as const;

/**
 * The blocking script that runs before first paint.
 *
 * Without it the server renders the light default, a reader who chose dark sees
 * it, and the client repaints a frame later — a flash on every navigation that
 * no amount of CSS fixes, because the choice lives in localStorage and the
 * server cannot read it.
 */
export const themeInitScript = `
(function () {
  try {
    var t = localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});
    if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
  } catch (e) {}
})();
`;
