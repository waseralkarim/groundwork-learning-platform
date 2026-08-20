import Link from "next/link";
import { notFound } from "next/navigation";

import { ApiError, getMyProgress, getOutline, getTopic } from "@/lib/api";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props) {
  const { slug } = await params;
  try {
    const topic = await getTopic(slug);
    return { title: topic.title, description: topic.summary };
  } catch {
    return { title: "Topic" };
  }
}

/**
 * The topic overview — a syllabus, not the content.
 *
 * It answers three questions and then gets out of the way: what will I be able
 * to do, what is in here, and where do I start. The content itself lives in the
 * player at /learn/[topic]/[step], one screen at a time.
 */
export default async function TopicPage({ params }: Props) {
  const { slug } = await params;

  let topic: Awaited<ReturnType<typeof getTopic>>;
  let outline: Awaited<ReturnType<typeof getOutline>>;
  try {
    [topic, outline] = await Promise.all([getTopic(slug), getOutline(slug)]);
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 404) notFound();
    throw cause;
  }

  const progress = await getMyProgress();
  const completed = new Set(
    (progress ?? []).filter((row) => row.status === "completed").map((row) => row.entity_id),
  );
  const doneCount = outline.steps.filter((step) => completed.has(step.entity_id)).length;
  const resumeStep =
    outline.steps.find((step) => !completed.has(step.entity_id)) ?? outline.steps[0];
  const started = doneCount > 0;

  const counts = outline.steps.reduce<Record<string, number>>((acc, step) => {
    acc[step.kind] = (acc[step.kind] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-12 flex flex-col gap-10">
      <nav className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.13em] text-[var(--color-muted)]">
        <Link href="/" className="hover:text-[var(--color-accent)]">
          Roadmap
        </Link>
        <span className="px-2">/</span>
        <span>{topic.course.title}</span>
      </nav>

      <header className="prose-measure flex flex-col gap-4">
        <div className="flex flex-wrap gap-x-4 gap-y-1 font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.13em] text-[var(--color-muted)]">
          <span>{topic.levels.join(" · ")}</span>
          <span>{topic.estimated_minutes} min</span>
          <span>{outline.steps.length} screens</span>
          <span>
            {topic.prerequisites.length === 0
              ? "No prerequisites"
              : `${topic.prerequisites.length} prerequisite(s)`}
          </span>
        </div>

        <h1 className="font-[family-name:var(--font-display)] text-4xl font-semibold leading-tight tracking-tight text-balance">
          {topic.title}
        </h1>
        <p className="text-[var(--color-ink-soft)]">{topic.summary}</p>

        {resumeStep ? (
          <div className="flex flex-wrap items-center gap-4 pt-1">
            <Link
              href={`/learn/${slug}/${resumeStep.slug}`}
              className="rounded-sm border border-[var(--color-accent)] bg-[var(--color-accent)] px-5 py-2.5 text-sm font-semibold text-[var(--color-surface)]"
            >
              {started ? "Resume" : "Start topic"}
            </Link>
            {started ? (
              <span className="font-[family-name:var(--font-mono)] text-[0.66rem] tabular-nums text-[var(--color-muted)]">
                {doneCount}/{outline.steps.length} done · next: {resumeStep.title}
              </span>
            ) : null}
          </div>
        ) : null}
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.14em] text-[var(--color-accent)]">
          What you will be able to do
        </h2>
        <ul className="prose-measure flex flex-col gap-2">
          {topic.objectives.map((objective) => (
            <li key={objective.code} className="flex gap-3 text-sm">
              <span className="shrink-0 font-[family-name:var(--font-mono)] text-[0.68rem] text-[var(--color-muted)]">
                {objective.level}
              </span>
              <span className="text-[var(--color-ink-soft)]">{objective.statement}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight">
          What is in here
        </h2>
        <div className="flex flex-wrap gap-x-8 gap-y-3">
          <Count label="Lessons" value={counts.lesson ?? 0} />
          <Count label="Hands-on labs" value={counts.lab ?? 0} />
          <Count label="Troubleshooting" value={counts.troubleshooting ?? 0} />
          <Count label="Quiz questions" value={topic.has_quiz ? 15 : 0} />
          <Count label="Interview questions" value={topic.interview_count} />
          <Count label="Assessment parts" value={topic.assessment_part_count} />
        </div>

        <ol className="mt-2 border-t border-[var(--color-rule)]">
          {outline.steps.map((step, index) => (
            <li key={step.slug}>
              <Link
                href={`/learn/${slug}/${step.slug}`}
                className="flex items-baseline gap-4 border-b border-[var(--color-rule-soft)] py-2.5 hover:text-[var(--color-accent)]"
              >
                <span className="w-6 shrink-0 font-[family-name:var(--font-mono)] text-[0.66rem] tabular-nums text-[var(--color-muted)]">
                  {completed.has(step.entity_id) ? (
                    <span className="text-[var(--color-signal)]">✓</span>
                  ) : (
                    String(index + 1).padStart(2, "0")
                  )}
                </span>
                <span className="min-w-0 flex-1 truncate text-[0.95rem]">{step.title}</span>
                <span className="shrink-0 font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.1em] text-[var(--color-muted)]">
                  {step.kind === "lesson" ? "read" : step.kind}
                </span>
              </Link>
            </li>
          ))}
        </ol>
      </section>

      {topic.terminology.length > 0 ? (
        <section className="flex flex-col gap-3">
          <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight">
            Terminology
          </h2>
          <dl className="border-t border-[var(--color-rule)]">
            {topic.terminology.map((entry) => (
              <div
                key={entry.term}
                className="grid gap-1 border-b border-[var(--color-rule-soft)] py-3 sm:grid-cols-[12rem_1fr] sm:gap-4"
              >
                <dt className="font-[family-name:var(--font-mono)] text-[0.8rem] text-[var(--color-accent)]">
                  {entry.term}
                </dt>
                <dd className="text-sm text-[var(--color-ink-soft)]">{entry.definition}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      {topic.foreshadows.length > 0 ? (
        <section className="prose-measure flex flex-col gap-3">
          <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight">
            Where this leads
          </h2>
          <ul className="flex flex-col gap-2">
            {topic.foreshadows.map((item) => (
              <li key={item} className="text-sm text-[var(--color-ink-soft)]">
                {item}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function Count({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-[family-name:var(--font-mono)] text-lg tabular-nums">{value}</span>
      <span className="font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
        {label}
      </span>
    </div>
  );
}
