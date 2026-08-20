"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { OutlineStep } from "@/lib/api";

/**
 * The bar at the bottom of every screen.
 *
 * One primary action — finish this and move on — because a learner who has to
 * decide what to do next after every screen loses momentum. Previous is present
 * but quiet.
 */
export function StepFooter({
  topicSlug,
  step,
  previous,
  next,
  index,
  total,
  initiallyDone,
  signedIn,
}: {
  topicSlug: string;
  step: OutlineStep;
  previous: OutlineStep | null;
  next: OutlineStep | null;
  index: number;
  total: number;
  initiallyDone: boolean;
  signedIn: boolean;
}) {
  const router = useRouter();
  const [done, setDone] = useState(initiallyDone);
  const [busy, setBusy] = useState(false);

  async function completeAndContinue() {
    setBusy(true);
    if (signedIn && !done) {
      await fetch(`/api/v1/topics/${topicSlug}/steps/${step.slug}/progress`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ status: "completed" }),
      }).catch(() => {});
      setDone(true);
    }
    if (next) {
      router.push(`/learn/${topicSlug}/${next.slug}`);
    } else {
      router.push(`/topics/${topicSlug}`);
    }
    router.refresh();
    setBusy(false);
  }

  return (
    <div className="sticky bottom-0 z-10 mt-10 flex flex-wrap items-center gap-x-4 gap-y-3 border-t border-[var(--color-rule)] bg-[var(--color-ground)]/95 px-1 py-4 backdrop-blur">
      {previous ? (
        <Link
          href={`/learn/${topicSlug}/${previous.slug}`}
          className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.11em] text-[var(--color-muted)] hover:text-[var(--color-accent)]"
        >
          ← Previous
        </Link>
      ) : (
        <span />
      )}

      <span className="font-[family-name:var(--font-mono)] text-[0.66rem] tabular-nums text-[var(--color-muted)]">
        {index + 1} / {total}
        {done ? <span className="ml-2 text-[var(--color-signal)]">✓ done</span> : null}
      </span>

      <button
        type="button"
        onClick={completeAndContinue}
        disabled={busy}
        className="ml-auto rounded-sm border border-[var(--color-accent)] bg-[var(--color-accent)] px-5 py-2 text-sm font-semibold text-[var(--color-surface)] disabled:opacity-50"
      >
        {next ? (done ? "Next" : "Complete and continue") : "Finish topic"}
      </button>
    </div>
  );
}
