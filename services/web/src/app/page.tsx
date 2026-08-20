import Link from "next/link";
import { ApiError, getRoadmap, type Roadmap } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let roadmap: Roadmap | null = null;
  let error: string | null = null;

  try {
    roadmap = await getRoadmap();
  } catch (cause) {
    error =
      cause instanceof ApiError && cause.status === 404
        ? "No content has been ingested yet. Run `task content:ingest`."
        : cause instanceof ApiError
          ? cause.message
          : "Unexpected error reaching the API";
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-12 flex flex-col gap-10">
      <header className="prose-measure flex flex-col gap-3">
        <span className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.16em] text-[var(--color-accent)]">
          Learning path
        </span>
        <h1 className="font-[family-name:var(--font-display)] text-4xl font-semibold leading-tight tracking-tight text-balance">
          {roadmap?.title ?? "Groundwork"}
        </h1>
        <p className="text-[var(--color-ink-soft)]">
          {roadmap?.summary ??
            "Build DevOps from the ground up — foundations, hands-on labs, and production reality."}
        </p>
      </header>

      {error ? (
        <div className="rounded-sm border border-[var(--color-accent)] bg-[var(--color-surface)] p-5">
          <p className="font-semibold">Nothing to show yet</p>
          <p className="mt-2 text-sm text-[var(--color-ink-soft)]">{error}</p>
        </div>
      ) : roadmap ? (
        <>
          <div className="flex flex-wrap gap-x-10 gap-y-3 border-y border-[var(--color-rule)] py-4">
            <Stat label="Courses" value={String(roadmap.courses.length)} />
            <Stat label="Topics published" value={String(roadmap.published_topics)} />
            <Stat
              label="Reading time"
              value={`${roadmap.courses.reduce((sum, c) => sum + c.estimated_hours, 0)} h`}
            />
            <Stat label="Content version" value={roadmap.content_version ?? "—"} />
          </div>

          <ol className="flex flex-col gap-4">
            {roadmap.courses.map((course) => (
              <li key={course.slug}>
                <article className="rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] p-6">
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <span className="font-[family-name:var(--font-mono)] text-sm font-semibold text-[var(--color-accent)]">
                      {course.code}
                    </span>
                    <h2 className="font-[family-name:var(--font-display)] text-xl font-semibold tracking-tight">
                      {course.title}
                    </h2>
                    <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
                      {course.track} · {course.levels.join(" ")} · {course.estimated_hours} h
                    </span>
                  </div>

                  <p className="prose-measure mt-3 text-sm text-[var(--color-ink-soft)]">
                    {course.summary}
                  </p>

                  {course.modules.map((module) => (
                    <div key={module.slug} className="mt-5">
                      <h3 className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.13em] text-[var(--color-muted)]">
                        {module.title}
                      </h3>
                      <ul className="mt-2 border-t border-[var(--color-rule-soft)]">
                        {module.topics.map((topic) => (
                          <li key={topic.slug}>
                            <Link
                              href={`/topics/${topic.slug}`}
                              className="flex items-baseline justify-between gap-4 border-b border-[var(--color-rule-soft)] py-2.5 hover:text-[var(--color-accent)]"
                            >
                              <span className="text-[0.95rem]">{topic.title}</span>
                              <span className="shrink-0 font-[family-name:var(--font-mono)] text-[0.68rem] tabular-nums text-[var(--color-muted)]">
                                {topic.levels.join(" ")} · {topic.estimated_minutes} min
                              </span>
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </article>
              </li>
            ))}
          </ol>

          <p className="prose-measure text-sm text-[var(--color-muted)]">
            The curriculum is built one topic at a time. Courses A02 through H50 are designed and
            ordered in <code>docs/curriculum/ROADMAP.md</code>; they appear here as they are
            written.
          </p>
        </>
      ) : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.13em] text-[var(--color-muted)]">
        {label}
      </span>
      <span className="font-[family-name:var(--font-mono)] text-lg tabular-nums">{value}</span>
    </div>
  );
}
