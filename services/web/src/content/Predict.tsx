"use client";

import { useState } from "react";

/**
 * `:::predict{question="..."}` — commit to an answer before seeing one.
 *
 * The same pedagogy as the troubleshooting hypothesis gate, applied to prose:
 * a learner who has guessed and been wrong remembers the correction, and a
 * learner who read the answer beside the question remembers neither. Lab 01
 * makes this explicit — "being briefly wrong here is the point" — and this is
 * the directive that lets a lesson do it too.
 *
 * The gate is client-side and the answer is in the page source, which is fine
 * and deliberate: this teaches, it does not grade. Nothing here is recorded and
 * nothing depends on it. Where a reveal actually protects something — the
 * troubleshooting solution — the gate is server-side and stays that way.
 */
export function Predict({ question, children }: { question?: string; children?: React.ReactNode }) {
  const [guess, setGuess] = useState("");
  const [revealed, setRevealed] = useState(false);

  return (
    <section className="my-8 rounded-sm border border-dashed border-[var(--color-rule)] p-5">
      <span className="mb-2 block font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.14em] text-[var(--color-accent)]">
        Predict
      </span>

      {question ? <p className="mb-3 text-sm">{question}</p> : null}

      {revealed ? (
        <>
          {guess.trim() ? (
            <p className="mb-3 border-l-2 border-[var(--color-rule)] pl-3 text-sm text-[var(--color-muted)]">
              You said: {guess}
            </p>
          ) : null}
          <div className="text-sm [&>p:last-child]:mb-0">{children}</div>
        </>
      ) : (
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            type="text"
            value={guess}
            onChange={(event) => setGuess(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && guess.trim()) setRevealed(true);
            }}
            placeholder="Your answer — a guess is fine"
            aria-label="Your prediction"
            className="flex-1 rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] px-3 py-1.5 text-sm"
          />
          <button
            type="button"
            onClick={() => setRevealed(true)}
            disabled={!guess.trim()}
            className="rounded-sm border border-[var(--color-accent)] px-4 py-1.5 text-sm font-semibold text-[var(--color-accent)] disabled:cursor-not-allowed disabled:border-[var(--color-rule)] disabled:text-[var(--color-muted)]"
          >
            Check
          </button>
        </div>
      )}
    </section>
  );
}
