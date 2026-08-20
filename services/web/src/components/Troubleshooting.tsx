"use client";

import { useState } from "react";
import type { Scenario } from "@/lib/api";

type Solution = {
  root_cause: string;
  method: string;
  resolution: string;
  hints: string[];
};

/**
 * A troubleshooting scenario.
 *
 * The solution is not in this component and is not in the page payload. It is
 * fetched only after a hypothesis is accepted, and the API returns 423 until
 * then. Gating in the UI alone would be a suggestion; gating in the API is a
 * rule.
 */
export function Troubleshooting({
  topicSlug,
  scenario,
}: {
  topicSlug: string;
  scenario: Scenario;
}) {
  const [hypothesis, setHypothesis] = useState("");
  const [solution, setSolution] = useState<Solution | null>(null);
  const [hintsShown, setHintsShown] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const posted = await fetch(
        `/api/v1/topics/${topicSlug}/troubleshooting/${scenario.id}/hypothesis`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ body: hypothesis }),
        },
      );

      if (posted.status === 401) {
        setError("Sign in first — your diagnosis is recorded against your account.");
        return;
      }
      if (!posted.ok) {
        const body = await posted.json().catch(() => ({}));
        setError(typeof body.detail === "string" ? body.detail : "Could not submit.");
        return;
      }

      const revealed = await fetch(
        `/api/v1/topics/${topicSlug}/troubleshooting/${scenario.id}/solution`,
      );
      if (!revealed.ok) {
        setError("Diagnosis recorded, but the solution could not be loaded.");
        return;
      }
      setSolution(await revealed.json());
    } catch {
      setError("Could not reach the server.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <p className="whitespace-pre-wrap text-[var(--color-ink-soft)]">{scenario.situation}</p>

      <section className="flex flex-col gap-2">
        <h3 className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.13em] text-[var(--color-muted)]">
          Symptoms
        </h3>
        <ul className="list-disc pl-5 text-sm">
          {scenario.symptoms.map((symptom) => (
            <li key={symptom}>{symptom}</li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.13em] text-[var(--color-muted)]">
          Evidence
        </h3>
        {scenario.artifacts.map((artifact) => (
          <figure key={artifact.label} className="flex flex-col gap-1">
            <figcaption className="font-[family-name:var(--font-mono)] text-[0.62rem] text-[var(--color-muted)]">
              {artifact.label}
            </figcaption>
            <pre className="overflow-x-auto rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface-2)] p-3 font-[family-name:var(--font-mono)] text-[0.76rem] leading-relaxed">
              {artifact.content}
            </pre>
          </figure>
        ))}
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.13em] text-[var(--color-muted)]">
          Answer these before you look
        </h3>
        <ul className="list-decimal pl-5 text-sm text-[var(--color-ink-soft)]">
          {scenario.diagnostic_questions.map((question) => (
            <li key={question}>{question}</li>
          ))}
        </ul>
      </section>

      {solution ? (
        <section className="flex flex-col gap-5 rounded-sm border border-[var(--color-signal)] bg-[var(--color-surface)] p-5">
          <Block title="Root cause" body={solution.root_cause} />
          <Block title="Method — the part that transfers" body={solution.method} />
          <Block title="Resolution" body={solution.resolution} />
        </section>
      ) : (
        <section className="flex flex-col gap-3 rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] p-5">
          <label className="flex flex-col gap-2">
            <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.13em] text-[var(--color-accent)]">
              Your diagnosis
            </span>
            <span className="text-sm text-[var(--color-ink-soft)]">
              Which resource is the bottleneck, and which line of output proves it? The solution
              unlocks once you have committed to an answer.
            </span>
            <textarea
              value={hypothesis}
              onChange={(event) => setHypothesis(event.target.value)}
              rows={4}
              className="rounded-sm border border-[var(--color-rule)] bg-[var(--color-ground)] p-3 text-sm"
              placeholder="It is memory-bound. vmstat shows si and so sustained around 1000…"
            />
          </label>

          {scenario.reveal_policy === "progressive" && hintsShown < 3 ? (
            <button
              type="button"
              onClick={() => setHintsShown((n) => n + 1)}
              className="self-start font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.12em] text-[var(--color-muted)] hover:text-[var(--color-accent)]"
            >
              I am stuck — narrow it down
            </button>
          ) : null}

          {hintsShown > 0 ? (
            <p className="border-l-2 border-[var(--color-rule)] pl-3 text-sm text-[var(--color-muted)]">
              Rule things out rather than looking for the answer. Three resources, three sets of
              columns — which two can you eliminate, and what evidence eliminates them?
            </p>
          ) : null}

          {error ? (
            <p role="alert" className="text-sm text-[var(--color-accent)]">
              {error}
            </p>
          ) : null}

          <button
            type="button"
            onClick={submit}
            disabled={busy || hypothesis.trim().length < 30}
            className="self-start rounded-sm border border-[var(--color-accent)] bg-[var(--color-accent)] px-4 py-2 text-sm font-semibold text-[var(--color-surface)] disabled:opacity-40"
          >
            {busy ? "Submitting…" : "Submit diagnosis and reveal"}
          </button>
          <span className="font-[family-name:var(--font-mono)] text-[0.62rem] text-[var(--color-muted)]">
            {hypothesis.trim().length}/30 characters minimum
          </span>
        </section>
      )}
    </div>
  );
}

function Block({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.13em] text-[var(--color-signal)]">
        {title}
      </h3>
      <p className="whitespace-pre-wrap text-sm text-[var(--color-ink-soft)]">{body}</p>
    </div>
  );
}
