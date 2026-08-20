"use client";

import { useLabShell } from "../components/lab/useLabShell";

/**
 * `:::try{lab=<slug> run="<command>"}` — a real shell, inline in a lesson.
 *
 * The gap this closes: a lesson could describe what `free -m` reports and show
 * canned output, but the learner never ran it. Reading about a command and
 * typing it are different kinds of knowing, and the second one is the product.
 *
 * The session is a normal lab session against a lab in the same topic, so the
 * image, the seed, the isolation tier, the TTL and the per-user quota are all
 * the ones that lab already declares. A lesson cannot ask for a shell the
 * learner could not have opened from the lab screen.
 */
export function TryIt({
  topicSlug,
  labSlug,
  title,
  run,
  children,
}: {
  topicSlug: string;
  labSlug: string;
  title?: string;
  run?: string;
  children?: React.ReactNode;
}) {
  const shell = useLabShell({ topicSlug, labSlug });

  return (
    <section className="my-8 rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)]">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-[var(--color-rule)] px-4 py-2.5">
        <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.14em] text-[var(--color-accent)]">
          Try it
        </span>
        {title ? <span className="text-sm">{title}</span> : null}

        {shell.status === "running" && shell.remaining !== null ? (
          <span
            className={`font-[family-name:var(--font-mono)] text-[0.66rem] tabular-nums ${
              shell.remaining < 300 ? "text-[var(--color-accent)]" : "text-[var(--color-muted)]"
            }`}
          >
            {Math.floor(shell.remaining / 60)}:{String(shell.remaining % 60).padStart(2, "0")} left
          </span>
        ) : null}

        <div className="ml-auto flex gap-2">
          {shell.status === "running" && run ? (
            <button
              type="button"
              onClick={() => shell.send(`${run}\n`)}
              className="rounded-sm border border-[var(--color-rule)] px-3 py-1 font-[family-name:var(--font-mono)] text-xs hover:border-[var(--color-accent)]"
            >
              Run {run}
            </button>
          ) : null}
          {shell.status === "idle" || shell.status === "ended" ? (
            <button
              type="button"
              onClick={shell.start}
              className="rounded-sm border border-[var(--color-accent)] bg-[var(--color-accent)] px-3 py-1 text-xs font-semibold text-[var(--color-surface)]"
            >
              {shell.status === "ended" ? "Start again" : "Open a shell"}
            </button>
          ) : null}
          {shell.status === "starting" ? (
            <span className="font-[family-name:var(--font-mono)] text-xs text-[var(--color-muted)]">
              starting…
            </span>
          ) : null}
          {shell.status === "running" ? (
            <button
              type="button"
              onClick={shell.end}
              className="rounded-sm border border-[var(--color-rule)] px-3 py-1 text-xs hover:border-[var(--color-accent)]"
            >
              Close
            </button>
          ) : null}
        </div>
      </header>

      {children ? (
        <div className="px-4 pt-3 text-sm text-[var(--color-ink-soft)] [&>p:last-child]:mb-0">
          {children}
        </div>
      ) : null}

      {shell.error ? (
        <p role="alert" className="px-4 py-3 text-sm text-[var(--color-accent)]">
          {shell.error}
        </p>
      ) : null}

      {shell.status === "ended" ? (
        <p className="px-4 py-3 text-sm text-[var(--color-muted)]">
          The container is gone and nothing you wrote survived it. That is the design.
        </p>
      ) : null}

      <div
        ref={shell.mountRef}
        className={
          shell.status === "running" || shell.status === "starting"
            ? "h-64 overflow-hidden px-2 py-2"
            : "hidden"
        }
      />
    </section>
  );
}
