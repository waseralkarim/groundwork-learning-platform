"use client";

import { useState } from "react";
import type { QuizPaper } from "@/lib/api";

type GradedQuestion = {
  id: string;
  stem: string;
  level: string;
  objectives: string[];
  given: string[];
  correct: string[];
  is_correct: boolean;
  explanation: string;
  options: { id: string; text: string; correct: boolean; note: string | null }[];
};

type Graded = {
  score: number;
  passed: boolean;
  pass_score: number;
  total: number;
  correct_count: number;
  questions: GradedQuestion[];
  weak_objectives: { code: string; statement: string; correct: number; total: number }[];
};

/**
 * The quiz.
 *
 * Note what this component does not have: the answer key. It cannot mark
 * anything. It collects choices, posts them, and renders whatever the server
 * says — which is the only arrangement in which a score means something.
 */
export function Quiz({ paper }: { paper: QuizPaper }) {
  const [answers, setAnswers] = useState<Record<string, string[]>>({});
  const [result, setResult] = useState<Graded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function choose(questionId: string, optionId: string, multi: boolean) {
    setAnswers((current) => {
      const existing = current[questionId] ?? [];
      if (!multi) return { ...current, [questionId]: [optionId] };
      return {
        ...current,
        [questionId]: existing.includes(optionId)
          ? existing.filter((id) => id !== optionId)
          : [...existing, optionId],
      };
    });
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const started = await fetch(`/api/v1/topics/${paper.topic_slug}/quiz/attempts`, {
        method: "POST",
      });
      if (started.status === 401) {
        setError("Sign in to take the quiz — attempts are recorded against your account.");
        return;
      }
      if (!started.ok) {
        const body = await started.json().catch(() => ({}));
        setError(typeof body.detail === "string" ? body.detail : "Could not start the quiz.");
        return;
      }

      const { attempt_id } = await started.json();
      const graded = await fetch(`/api/v1/quiz/attempts/${attempt_id}/submit`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ answers }),
      });
      if (!graded.ok) {
        setError("Could not submit the quiz.");
        return;
      }
      setResult(await graded.json());
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch {
      setError("Could not reach the server.");
    } finally {
      setBusy(false);
    }
  }

  const answered = Object.values(answers).filter((value) => value.length > 0).length;

  if (result) {
    return <Results result={result} onRetry={() => setResult(null)} />;
  }

  return (
    <div className="flex flex-col gap-8">
      <ol className="flex flex-col gap-8">
        {paper.questions.map((question, index) => {
          const multi = question.type === "multi_choice";
          return (
            <li key={question.id} className="flex flex-col gap-3">
              <div className="flex items-baseline gap-3">
                <span className="font-[family-name:var(--font-mono)] text-[0.66rem] tabular-nums text-[var(--color-muted)]">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] text-[var(--color-signal)]">
                  {question.level}
                </span>
                {multi ? (
                  <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
                    select all
                  </span>
                ) : null}
              </div>

              <p className="whitespace-pre-wrap font-medium">{question.stem}</p>

              <div className="flex flex-col gap-2">
                {question.options.map((option) => {
                  const selected = (answers[question.id] ?? []).includes(option.id);
                  return (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => choose(question.id, option.id, multi)}
                      aria-pressed={selected}
                      className={`flex items-start gap-3 rounded-sm border px-3 py-2 text-left text-sm ${
                        selected
                          ? "border-[var(--color-accent)] bg-[var(--color-surface)]"
                          : "border-[var(--color-rule)] bg-[var(--color-surface)] hover:border-[var(--color-muted)]"
                      }`}
                    >
                      <span className="font-[family-name:var(--font-mono)] text-[0.7rem] text-[var(--color-muted)]">
                        {option.id}
                      </span>
                      <span>{option.text}</span>
                    </button>
                  );
                })}
              </div>
            </li>
          );
        })}
      </ol>

      {error ? (
        <p
          role="alert"
          className="rounded-sm border border-[var(--color-accent)] bg-[var(--color-surface)] px-3 py-2 text-sm"
        >
          {error}
        </p>
      ) : null}

      <div className="flex items-center gap-4 border-t border-[var(--color-rule)] pt-5">
        <button
          type="button"
          onClick={submit}
          disabled={busy}
          className="rounded-sm border border-[var(--color-accent)] bg-[var(--color-accent)] px-4 py-2 text-sm font-semibold text-[var(--color-surface)] disabled:opacity-50"
        >
          {busy ? "Grading…" : "Submit"}
        </button>
        <span className="font-[family-name:var(--font-mono)] text-[0.68rem] tabular-nums text-[var(--color-muted)]">
          {answered}/{paper.question_count} answered · pass at {paper.pass_score}%
        </span>
      </div>
    </div>
  );
}

function Results({ result, onRetry }: { result: Graded; onRetry: () => void }) {
  return (
    <div className="flex flex-col gap-8">
      <div
        className={`rounded-sm border p-5 ${
          result.passed
            ? "border-[var(--color-signal)] bg-[var(--color-surface)]"
            : "border-[var(--color-accent)] bg-[var(--color-surface)]"
        }`}
      >
        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
          <span className="font-[family-name:var(--font-display)] text-3xl font-semibold tabular-nums">
            {result.score}%
          </span>
          <span className="font-[family-name:var(--font-mono)] text-[0.68rem] uppercase tracking-[0.13em]">
            {result.passed ? "passed" : `not yet — ${result.pass_score}% needed`}
          </span>
          <span className="font-[family-name:var(--font-mono)] text-[0.68rem] tabular-nums text-[var(--color-muted)]">
            {result.correct_count}/{result.total} correct
          </span>
        </div>

        {result.weak_objectives.length > 0 ? (
          <div className="mt-4 border-t border-[var(--color-rule-soft)] pt-3">
            <p className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.13em] text-[var(--color-muted)]">
              Go back to these
            </p>
            <ul className="mt-2 flex flex-col gap-1.5">
              {result.weak_objectives.map((objective) => (
                <li key={objective.code} className="text-sm text-[var(--color-ink-soft)]">
                  <span className="font-[family-name:var(--font-mono)] text-[0.7rem] text-[var(--color-muted)]">
                    {objective.code} ({objective.correct}/{objective.total}){" "}
                  </span>
                  {objective.statement}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      <ol className="flex flex-col gap-7">
        {result.questions.map((question) => (
          <li key={question.id} className="flex flex-col gap-2">
            <div className="flex items-baseline gap-3">
              <span
                className={`font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] ${
                  question.is_correct ? "text-[var(--color-signal)]" : "text-[var(--color-accent)]"
                }`}
              >
                {question.is_correct ? "correct" : "wrong"}
              </span>
              <span className="font-[family-name:var(--font-mono)] text-[0.62rem] text-[var(--color-muted)]">
                {question.id} · {question.level}
              </span>
            </div>

            <p className="whitespace-pre-wrap font-medium">{question.stem}</p>

            <ul className="flex flex-col gap-1.5">
              {question.options.map((option) => {
                const chosen = question.given.includes(option.id);
                return (
                  <li
                    key={option.id}
                    className={`rounded-sm border px-3 py-2 text-sm ${
                      option.correct
                        ? "border-[var(--color-signal)]"
                        : chosen
                          ? "border-[var(--color-accent)]"
                          : "border-[var(--color-rule-soft)]"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="font-[family-name:var(--font-mono)] text-[0.7rem] text-[var(--color-muted)]">
                        {option.id}
                      </span>
                      <div className="flex flex-col gap-1">
                        <span>
                          {option.text}
                          {option.correct ? (
                            <span className="ml-2 font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.1em] text-[var(--color-signal)]">
                              correct
                            </span>
                          ) : null}
                          {chosen && !option.correct ? (
                            <span className="ml-2 font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.1em] text-[var(--color-accent)]">
                              you chose
                            </span>
                          ) : null}
                        </span>
                        {option.note ? (
                          <span className="text-xs text-[var(--color-muted)]">{option.note}</span>
                        ) : null}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>

            <p className="border-l-2 border-[var(--color-rule)] pl-3 text-sm text-[var(--color-ink-soft)]">
              {question.explanation}
            </p>
          </li>
        ))}
      </ol>

      <button
        type="button"
        onClick={onRetry}
        className="self-start rounded-sm border border-[var(--color-rule)] px-4 py-2 text-sm hover:border-[var(--color-accent)]"
      >
        Try again
      </button>
    </div>
  );
}
