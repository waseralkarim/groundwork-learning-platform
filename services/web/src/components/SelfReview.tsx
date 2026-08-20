"use client";

import { useState } from "react";
import type { RubricCriterion } from "@/lib/api";

type Score = "inadequate" | "adequate" | "excellent";

/**
 * Rubric-based self-review.
 *
 * The form is deliberately awkward in one specific way: every criterion needs a
 * score *and* a piece of evidence before it will submit. That friction is the
 * feature. A rubric you can fill in by clicking "excellent" five times collects
 * nothing, and the server rejects it anyway — this just says so earlier.
 *
 * The descriptors are shown before the learner picks, not after, so the choice
 * is made against a written standard rather than a feeling.
 */
export function SelfReview({ slug, rubric }: { slug: string; rubric: RubricCriterion[] }) {
  const [scores, setScores] = useState<Record<string, Score>>({});
  const [evidence, setEvidence] = useState<Record<string, string>>({});
  const [artifactUrl, setArtifactUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "done">("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<number | null>(null);

  const incomplete = rubric.filter(
    (criterion) => !scores[criterion.id] || (evidence[criterion.id] ?? "").trim().length < 10,
  );

  async function submit() {
    setState("sending");
    setError(null);
    try {
      const response = await fetch(`/api/v1/projects/${encodeURIComponent(slug)}/submissions`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          artifact_url: artifactUrl.trim() || null,
          notes,
          scores: rubric.map((criterion) => ({
            criterion_id: criterion.id,
            score: scores[criterion.id],
            evidence: evidence[criterion.id],
          })),
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setError(typeof body.detail === "string" ? body.detail : "Could not save your review.");
        setState("idle");
        return;
      }
      const saved = await response.json();
      setResult(saved.self_score);
      setState("done");
    } catch {
      setError("Could not reach the server.");
      setState("idle");
    }
  }

  if (state === "done") {
    return (
      <section className="mt-10 rounded-sm border border-[var(--color-signal)] bg-[var(--color-surface)] p-5">
        <h2 className="text-lg font-semibold">Review saved</h2>
        <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
          Your own weighted score was <strong className="tabular-nums">{result}/100</strong>.
        </p>
        {/* Said plainly, because a learner will otherwise assume it counts. */}
        <p className="mt-3 text-xs text-[var(--color-muted)]">
          This score is yours. It does not contribute to your competence figures and it does not
          unlock anything — self-assessment that unlocks something stops being self-assessment. Its
          value is comparing it against the review you write after your next attempt.
        </p>
      </section>
    );
  }

  return (
    <section className="mt-10">
      <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight">
        Review your own work
      </h2>
      <p className="prose-measure mt-1 text-sm text-[var(--color-ink-soft)]">
        Read the descriptors before choosing, and point at something concrete for each one. Marking
        yourself down where you deserve it is the entire value of the exercise.
      </p>

      <ol className="mt-6 flex flex-col gap-6">
        {rubric.map((criterion) => (
          <li
            key={criterion.id}
            className="rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] p-4"
          >
            <div className="flex items-baseline gap-3">
              <span className="font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.14em] text-[var(--color-muted)]">
                {criterion.id} · weight {criterion.weight}
              </span>
            </div>
            <h3 className="mt-1 text-base font-semibold">{criterion.criterion}</h3>

            <dl className="mt-3 flex flex-col gap-1.5 text-xs text-[var(--color-ink-soft)]">
              {(["excellent", "adequate", "inadequate"] as const).map((level) => (
                <div key={level} className="flex gap-2">
                  <dt className="w-20 shrink-0 font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.1em] text-[var(--color-muted)]">
                    {level}
                  </dt>
                  <dd>{criterion[level]}</dd>
                </div>
              ))}
            </dl>

            <div className="mt-3 flex flex-wrap gap-2">
              {(["inadequate", "adequate", "excellent"] as const).map((level) => (
                <button
                  key={level}
                  type="button"
                  onClick={() => setScores((s) => ({ ...s, [criterion.id]: level }))}
                  className={`rounded-sm border px-3 py-1 font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.1em] ${
                    scores[criterion.id] === level
                      ? "border-[var(--color-accent)] text-[var(--color-accent)]"
                      : "border-[var(--color-rule)] text-[var(--color-muted)] hover:border-[var(--color-accent)]"
                  }`}
                >
                  {level}
                </button>
              ))}
            </div>

            <label className="mt-3 flex flex-col gap-1">
              <span className="text-xs text-[var(--color-muted)]">{criterion.evidence}</span>
              <textarea
                value={evidence[criterion.id] ?? ""}
                onChange={(event) =>
                  setEvidence((e) => ({ ...e, [criterion.id]: event.target.value }))
                }
                rows={2}
                className="rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface-2)] px-3 py-2 text-sm"
              />
            </label>
          </li>
        ))}
      </ol>

      <div className="mt-6 flex flex-col gap-4">
        <label className="flex flex-col gap-1">
          <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
            Link to your work (optional)
          </span>
          <input
            type="url"
            value={artifactUrl}
            onChange={(event) => setArtifactUrl(event.target.value)}
            placeholder="https://github.com/you/your-report"
            className="rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] px-3 py-2 text-sm"
          />
          {/* Worth saying: people assume anything they paste gets fetched. */}
          <span className="text-xs text-[var(--color-muted)]">
            Stored and shown back to you. The platform never opens it.
          </span>
        </label>

        <label className="flex flex-col gap-1">
          <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
            Notes to your future self
          </span>
          <textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            rows={4}
            className="rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] px-3 py-2 text-sm"
          />
        </label>
      </div>

      {error ? (
        <p role="alert" className="mt-4 text-sm text-[var(--color-accent)]">
          {error}
        </p>
      ) : null}

      <div className="mt-5 flex flex-wrap items-center gap-4">
        <button
          type="button"
          onClick={submit}
          disabled={incomplete.length > 0 || state === "sending"}
          className="rounded-sm border border-[var(--color-accent)] bg-[var(--color-accent)] px-4 py-2 text-sm font-semibold text-[var(--color-surface)] disabled:cursor-not-allowed disabled:border-[var(--color-rule)] disabled:bg-transparent disabled:text-[var(--color-muted)]"
        >
          {state === "sending" ? "Saving…" : "Save my review"}
        </button>
        {incomplete.length > 0 ? (
          <span className="text-xs text-[var(--color-muted)]">
            {incomplete.length} criterion{incomplete.length === 1 ? "" : "a"} still needs a score
            and evidence
          </span>
        ) : null}
      </div>
    </section>
  );
}
