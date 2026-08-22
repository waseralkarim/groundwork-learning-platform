import Link from "next/link";
import { ApiError, getRoadmap, type Roadmap, type RoadmapCourse } from "@/lib/api";

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

  const tracks = roadmap ? groupByTrack(roadmap.courses) : [];
  const hours = roadmap?.courses.reduce((sum, c) => sum + c.estimated_hours, 0) ?? 0;
  const firstTopic = roadmap?.courses[0]?.modules[0]?.topics[0] ?? null;

  return (
    <div className="flex flex-col">
      <section className="relative overflow-hidden border-b border-[var(--color-rule)]">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-[0.07] [background:radial-gradient(60rem_28rem_at_18%_-10%,var(--color-accent),transparent_70%)]"
        />
        <div className="relative mx-auto w-full max-w-6xl px-6 py-20 sm:py-24">
          <div className="flex max-w-3xl flex-col gap-6">
            <span className="inline-flex w-fit items-center gap-2 rounded-full border border-[var(--color-rule)] bg-[var(--color-surface)] px-3 py-1 font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.16em] text-[var(--color-accent)]">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--color-accent)]" />
              Learning path
            </span>

            <h1 className="font-[family-name:var(--font-display)] text-[clamp(2.5rem,6vw,4.25rem)] font-semibold leading-[1.02] tracking-tight text-balance">
              {roadmap?.title ?? "Groundwork"}
            </h1>

            <p className="max-w-2xl text-[1.1rem] leading-relaxed text-[var(--color-ink-soft)]">
              {roadmap?.summary ??
                "Build DevOps from the ground up — foundations, hands-on labs, and production reality."}
            </p>

            {firstTopic ? (
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2">
                <Link
                  href={`/topics/${firstTopic.slug}`}
                  className="inline-flex items-center gap-2 rounded-full bg-[var(--color-accent)] px-5 py-2.5 text-sm font-semibold text-[var(--color-surface)] transition-opacity hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)]"
                >
                  Start here
                  <span aria-hidden="true">→</span>
                </Link>
                <span className="text-sm text-[var(--color-muted)]">
                  Begin with{" "}
                  <span className="text-[var(--color-ink-soft)]">{firstTopic.title}</span> ·{" "}
                  {firstTopic.estimated_minutes} min
                </span>
              </div>
            ) : null}
          </div>
        </div>
      </section>

      <div className="mx-auto w-full max-w-6xl px-6 py-14 flex flex-col gap-16">
        {error ? (
          <div className="rounded-lg border border-[var(--color-accent)] bg-[var(--color-surface)] p-6">
            <p className="font-semibold">Nothing to show yet</p>
            <p className="mt-2 text-sm text-[var(--color-ink-soft)]">{error}</p>
          </div>
        ) : roadmap ? (
          <>
            <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-[var(--color-rule)] bg-[var(--color-rule)] sm:grid-cols-4">
              <Stat label="Courses" value={String(roadmap.courses.length)} />
              <Stat label="Topics" value={String(roadmap.published_topics)} />
              <Stat label="Hours" value={String(hours)} />
              <Stat label="Tracks" value={String(tracks.length)} />
            </dl>

            {tracks.map(([track, courses], trackIndex) => (
              <section key={track} className="flex flex-col gap-7">
                <div className="flex items-baseline gap-4">
                  <span className="font-[family-name:var(--font-mono)] text-[0.7rem] tabular-nums text-[var(--color-accent)]">
                    {String(trackIndex + 1).padStart(2, "0")}
                  </span>
                  <h2 className="font-[family-name:var(--font-display)] text-[1.75rem] font-semibold tracking-tight">
                    {track}
                  </h2>
                  <span className="h-px flex-1 bg-[var(--color-rule)]" aria-hidden="true" />
                  <span className="font-[family-name:var(--font-mono)] text-[0.64rem] uppercase tracking-[0.13em] tabular-nums text-[var(--color-muted)]">
                    {plural(courses.length, "course")}
                  </span>
                </div>

                <ul className="grid gap-5 md:grid-cols-2">
                  {courses.map((course, i) => (
                    <li key={course.slug}>
                      <CourseCard course={course} highlight={trackIndex === 0 && i === 0} />
                    </li>
                  ))}
                </ul>
              </section>
            ))}

            <p className="max-w-2xl border-t border-[var(--color-rule)] pt-6 text-sm leading-relaxed text-[var(--color-muted)]">
              The curriculum is built one topic at a time. Courses through H50 are designed and
              ordered in <code>docs/curriculum/ROADMAP.md</code>; they appear here as they are
              written.
            </p>
          </>
        ) : null}
      </div>
    </div>
  );
}

function CourseCard({ course, highlight }: { course: RoadmapCourse; highlight: boolean }) {
  const topicCount = course.modules.reduce((n, m) => n + m.topics.length, 0);

  return (
    <article className="group relative flex h-full flex-col gap-4 overflow-hidden rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-6 transition-all duration-200 hover:-translate-y-0.5 hover:border-[var(--color-accent)] hover:shadow-lg hover:shadow-black/5">
      <span
        aria-hidden="true"
        className="absolute inset-y-0 left-0 w-[3px] bg-[var(--color-accent)] opacity-0 transition-opacity duration-200 group-hover:opacity-100"
      />

      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-[family-name:var(--font-mono)] text-[0.7rem] font-semibold tracking-[0.08em] text-[var(--color-accent)]">
              {course.code}
            </span>
            {highlight ? (
              <span className="rounded-full border border-[var(--color-accent)] px-2 py-0.5 font-[family-name:var(--font-mono)] text-[0.56rem] uppercase tracking-[0.12em] text-[var(--color-accent)]">
                Start here
              </span>
            ) : null}
          </div>
          <h3 className="font-[family-name:var(--font-display)] text-[1.3rem] font-semibold leading-snug tracking-tight text-balance">
            {course.title}
          </h3>
        </div>
        <span className="shrink-0 font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] tabular-nums text-[var(--color-muted)]">
          {course.estimated_hours} h
        </span>
      </div>

      <p className="text-[0.9rem] leading-relaxed text-[var(--color-ink-soft)]">{course.summary}</p>

      <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1.5 pt-1 font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
        <span className="rounded border border-[var(--color-rule-soft)] px-1.5 py-0.5 text-[var(--color-signal)]">
          {course.levels.join(" ")}
        </span>
        <span className="tabular-nums">{plural(course.modules.length, "module")}</span>
        <span aria-hidden="true">·</span>
        <span className="tabular-nums">{plural(topicCount, "topic")}</span>
      </div>

      {topicCount > 0 ? (
        <details className="group/d border-t border-[var(--color-rule-soft)] pt-3">
          <summary className="flex cursor-pointer list-none items-center gap-2 font-[family-name:var(--font-mono)] text-[0.64rem] uppercase tracking-[0.12em] text-[var(--color-muted)] transition-colors hover:text-[var(--color-accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)]">
            <span
              aria-hidden="true"
              className="inline-block transition-transform duration-200 group-open/d:rotate-90"
            >
              ›
            </span>
            <span className="select-none">Contents</span>
          </summary>

          <div className="mt-3 flex flex-col gap-4">
            {course.modules.map((module) => (
              <div key={module.slug}>
                <h4 className="font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.13em] text-[var(--color-muted)]">
                  {module.title}
                </h4>
                <ul className="mt-1.5">
                  {module.topics.map((topic) => (
                    <li key={topic.slug}>
                      <Link
                        href={`/topics/${topic.slug}`}
                        className="flex items-baseline justify-between gap-3 border-b border-[var(--color-rule-soft)] py-2 text-sm transition-colors hover:text-[var(--color-accent)]"
                      >
                        <span>{topic.title}</span>
                        <span className="shrink-0 font-[family-name:var(--font-mono)] text-[0.62rem] tabular-nums text-[var(--color-muted)]">
                          {topic.estimated_minutes} min
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </article>
  );
}

function groupByTrack(courses: RoadmapCourse[]): Array<[string, RoadmapCourse[]]> {
  const byTrack = new Map<string, RoadmapCourse[]>();
  for (const course of courses) {
    const list = byTrack.get(course.track);
    if (list) list.push(course);
    else byTrack.set(course.track, [course]);
  }
  return [...byTrack.entries()];
}

function plural(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 bg-[var(--color-surface)] px-5 py-5">
      <dt className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.13em] text-[var(--color-muted)]">
        {label}
      </dt>
      <dd className="font-[family-name:var(--font-display)] text-[1.9rem] font-semibold leading-none tabular-nums">
        {value}
      </dd>
    </div>
  );
}
