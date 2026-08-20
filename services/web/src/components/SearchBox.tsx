"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

/**
 * The header search box.
 *
 * Suggestions come from titles only, and they are a navigation aid rather than
 * a result list — picking one runs the search rather than jumping straight to a
 * page, because a title match is not always the thing the learner wanted.
 */
export function SearchBox({ initialQuery = "" }: { initialQuery?: string }) {
  const router = useRouter();
  const [query, setQuery] = useState(initialQuery);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (query.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    // Debounced, and aborted on the next keystroke — otherwise a fast typist
    // gets results for a prefix they have already moved past.
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(
          `/api/v1/search/suggest?q=${encodeURIComponent(query.trim())}`,
          { signal: controller.signal },
        );
        if (response.ok) setSuggestions(await response.json());
      } catch {
        // An aborted request is the normal case, not an error worth showing.
      }
    }, 180);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  useEffect(() => {
    function onClickAway(event: MouseEvent) {
      if (!boxRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickAway);
    return () => document.removeEventListener("mousedown", onClickAway);
  }, []);

  function go(term: string) {
    const trimmed = term.trim();
    if (trimmed.length < 2) return;
    setOpen(false);
    router.push(`/search?q=${encodeURIComponent(trimmed)}`);
  }

  return (
    <search ref={boxRef} className="relative block">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          go(query);
        }}
      >
        <input
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(event) => {
            if (event.key === "Escape") setOpen(false);
          }}
          placeholder="Search the curriculum"
          aria-label="Search the curriculum"
          className="w-44 rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface-2)] px-3 py-1 font-[family-name:var(--font-mono)] text-[0.72rem] focus:w-64 focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)] sm:w-56"
        />
      </form>

      {open && suggestions.length > 0 ? (
        <ul className="absolute right-0 z-20 mt-1 w-80 overflow-hidden rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] shadow-lg">
          {suggestions.map((suggestion) => (
            <li key={suggestion}>
              <button
                type="button"
                onClick={() => go(suggestion)}
                className="block w-full truncate px-3 py-1.5 text-left text-[0.78rem] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-accent)]"
              >
                {suggestion}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </search>
  );
}
