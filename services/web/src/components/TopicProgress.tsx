"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function TopicProgress({
  slug,
  initialStatus,
  signedIn,
}: {
  slug: string;
  initialStatus: string | null;
  signedIn: boolean;
}) {
  const router = useRouter();
  const [status, setStatus] = useState(initialStatus);
  const [busy, setBusy] = useState(false);

  async function mark(next: "completed" | "in_progress") {
    setBusy(true);
    const response = await fetch(`/api/v1/topics/${slug}/progress`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ status: next }),
    }).catch(() => null);

    if (response?.ok) {
      const row = await response.json();
      setStatus(row.status);
      router.refresh();
    }
    setBusy(false);
  }

  if (!signedIn) {
    return (
      <a
        href="/login"
        className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.12em] text-[var(--color-accent)]"
      >
        Sign in to track progress
      </a>
    );
  }

  if (status === "completed") {
    return (
      <div className="flex items-center gap-3">
        <span className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.12em] text-[var(--color-signal)]">
          ✓ Completed
        </span>
        <button
          type="button"
          onClick={() => mark("in_progress")}
          disabled={busy}
          className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.1em] text-[var(--color-muted)] hover:text-[var(--color-accent)]"
        >
          undo
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => mark("completed")}
      disabled={busy}
      className="rounded-sm border border-[var(--color-accent)] px-3 py-1.5 font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.12em] text-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-[var(--color-surface)] disabled:opacity-50"
    >
      {busy ? "…" : "Mark complete"}
    </button>
  );
}
