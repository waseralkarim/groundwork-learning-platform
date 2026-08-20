"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import type { OutlineStep, TopicOutline } from "@/lib/api";

/**
 * The course outline.
 *
 * Persistent, grouped, and always showing where you are and what is left. This
 * is the difference between a learning platform and a documentation site: a
 * learner should never have to scroll to find out how much remains, and should
 * never lose their place by following a link.
 *
 * Grouped by *what you are doing*, not by content type — read it, do it, prove
 * it. That ordering is the pedagogy made visible.
 */

const GROUPS: { id: string; label: string; kinds: string[] }[] = [
  { id: "read", label: "Learn", kinds: ["lesson"] },
  { id: "practise", label: "Practise", kinds: ["lab", "exercise"] },
  { id: "diagnose", label: "Diagnose", kinds: ["troubleshooting"] },
  { id: "prove", label: "Prove it", kinds: ["quiz", "assessment", "interview"] },
];

const KIND_GLYPH: Record<string, string> = {
  lesson: "▤",
  lab: "▶",
  exercise: "✎",
  troubleshooting: "⚑",
  quiz: "◇",
  assessment: "◈",
  interview: "☰",
};

export function CourseSidebar({
  outline,
  completed,
}: {
  outline: TopicOutline;
  completed: string[];
}) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const done = new Set(completed);

  const currentSlug = pathname.split("/").pop() ?? "";
  const total = outline.steps.length;
  const doneCount = outline.steps.filter((s) => done.has(s.entity_id)).length;
  const percent = total ? Math.round((100 * doneCount) / total) : 0;

  const grouped = GROUPS.map((group) => ({
    ...group,
    steps: outline.steps.filter((step) => group.kinds.includes(step.kind)),
  })).filter((group) => group.steps.length > 0);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="sticky top-0 z-20 flex w-full items-center gap-3 border-b border-[var(--color-rule)] bg-[var(--color-surface)] px-5 py-3 text-left lg:hidden"
      >
        <span className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.12em] text-[var(--color-accent)]">
          {open ? "Hide" : "Contents"}
        </span>
        <span className="font-[family-name:var(--font-mono)] text-[0.66rem] tabular-nums text-[var(--color-muted)]">
          {doneCount}/{total}
        </span>
      </button>

      <aside
        className={`${
          open ? "block" : "hidden"
        } shrink-0 border-b border-[var(--color-rule)] bg-[var(--color-surface)] lg:sticky lg:top-0 lg:block lg:h-dvh lg:w-[19rem] lg:overflow-y-auto lg:border-b-0 lg:border-r`}
      >
        <div className="flex flex-col gap-4 px-5 py-6">
          <div className="flex flex-col gap-1">
            <Link
              href="/"
              className="font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.14em] text-[var(--color-muted)] hover:text-[var(--color-accent)]"
            >
              ← {outline.course.title}
            </Link>
            <h2 className="font-[family-name:var(--font-display)] text-lg font-semibold leading-tight tracking-tight">
              {outline.topic_title}
            </h2>
          </div>

          <div className="flex flex-col gap-1.5">
            <div className="flex items-baseline justify-between font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
              <span>
                {doneCount} of {total} done
              </span>
              <span className="tabular-nums">{percent}%</span>
            </div>
            <div
              className="h-1 w-full overflow-hidden rounded-full bg-[var(--color-rule)]"
              role="progressbar"
              aria-valuenow={percent}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Topic progress"
            >
              <div
                className="h-full bg-[var(--color-accent)] transition-[width] duration-500"
                style={{ width: `${percent}%` }}
              />
            </div>
          </div>

          <nav className="flex flex-col gap-5">
            {grouped.map((group) => (
              <div key={group.id} className="flex flex-col gap-1">
                <h3 className="font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.14em] text-[var(--color-muted)]">
                  {group.label}
                </h3>
                <ul className="flex flex-col">
                  {group.steps.map((step) => (
                    <SidebarItem
                      key={step.slug}
                      step={step}
                      topicSlug={outline.topic_slug}
                      current={step.slug === currentSlug}
                      done={done.has(step.entity_id)}
                      onNavigate={() => setOpen(false)}
                    />
                  ))}
                </ul>
              </div>
            ))}
          </nav>
        </div>
      </aside>
    </>
  );
}

function SidebarItem({
  step,
  topicSlug,
  current,
  done,
  onNavigate,
}: {
  step: OutlineStep;
  topicSlug: string;
  current: boolean;
  done: boolean;
  onNavigate: () => void;
}) {
  return (
    <li>
      <Link
        href={`/learn/${topicSlug}/${step.slug}`}
        onClick={onNavigate}
        aria-current={current ? "page" : undefined}
        className={`flex items-start gap-2.5 rounded-sm px-2 py-1.5 text-[0.82rem] leading-snug transition-colors ${
          current
            ? "bg-[var(--color-surface-2)] font-medium text-[var(--color-accent)]"
            : "text-[var(--color-ink-soft)] hover:bg-[var(--color-surface-2)]"
        }`}
      >
        <span
          className={`mt-[0.15rem] w-3 shrink-0 text-center font-[family-name:var(--font-mono)] text-[0.7rem] ${
            done ? "text-[var(--color-signal)]" : "text-[var(--color-muted)]"
          }`}
          aria-hidden="true"
        >
          {done ? "✓" : (KIND_GLYPH[step.kind] ?? "·")}
        </span>
        <span className="flex min-w-0 flex-col">
          <span className="truncate">{step.title}</span>
          {step.estimated_minutes ? (
            <span className="font-[family-name:var(--font-mono)] text-[0.6rem] text-[var(--color-muted)]">
              {step.estimated_minutes} min
            </span>
          ) : null}
        </span>
      </Link>
    </li>
  );
}
