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

  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-14 flex flex-col gap-14">
      <header className="flex flex-col gap-4">
        <Eyebrow>Learning path</Eyebrow>
        <h1 className="prose-measure font-[family-name:var(--font-display)] text-[clamp(2.25rem,5vw,3.5rem)] font-semibold leading-[1.05] tracking-tight text-balance">
          {roadmap?.title ?? "Groundwork"}
        </h1>
        <p className="prose-measure text-[1.05rem] leading-relaxed text-[var(--color-ink-soft)]">
          {roadmap?.summary ??
            "Build DevOps from the ground up — foundations, hands-on labs, and production reality."}
        </p>
      </header>

      {error ? (
        <div className="rounded-md border border-[var(--color-accent)] bg-[var(--color-surface)] p-5">
          <p className="font-semibold">Nothing to show yet</p>
          <p className="mt-2 text-sm text-[var(--color-ink-soft)]">{error}</p>
        </div>
      ) : roadmap ? (
        <>
          <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-[var(--color-rule)] bg-[var(--color-rule)] sm:grid-cols-4">
            <Stat label="Courses" value={String(roadmap.courses.length)} />
            <Stat label="Topics" value={String(roadmap.published_topics)} />
            <Stat label="Est. hours" value={String(hours)} />
            <Stat label="Tracks" value={String(tracks.length)} />
          </dl>

          {tracks.map(([track, courses]) => (
            <section key={track} className="flex flex-col gap-6">
              <div className="flex items-baseline gap-4">
                <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight">
                  {track}
                </h2>
                <span className="h-px flex-1 bg-[var(--color-rule)]" aria-hidden="true" />
                <span className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.13em] tabular-nums text-[var(--color-muted)]">
                  {plural(courses.length, "course")}
                </span>
              </div>

              <ul className="grid gap-5 md:grid-cols-2">
                {courses.map((course) => (
                  <li key={course.slug}>
                    <CourseCard course={course} />
                  </li>
                ))}
              </ul>
            </section>
          ))}

          <p className="prose-measure border-t border-[var(--color-rule)] pt-6 text-sm text-[var(--color-muted)]">
            The curriculum is built one topic at a time. Courses through H50 are designed and
            ordered in <code>docs/curriculum/ROADMAP.md</code>; they appear here as they are
            written.
          </p>
        </>
      ) : null}
    </div>
  );
}

function CourseCard({ course }: { course: RoadmapCourse }) {
  const topicCount = course.modules.reduce((n, m) => n + m.topics.length, 0);
  const moduleCount = course.modules.length;

  return (
    <article className="group flex h-full flex-col gap-4 rounded-md border border-[var(--color-rule)] bg-[var(--color-surface)] p-6 transition-colors hover:border-[var(--color-accent)]">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <span className="font-[family-name:var(--font-mono)] text-[0.7rem] font-semibold tracking-[0.08em] text-[var(--color-accent)]">
            {course.code}
          </span>
          <h3 className="font-[family-name:var(--font-display)] text-xl font-semibold leading-snug tracking-tight text-balance">
            {course.title}
          </h3>
        </div>
        <span className="shrink-0 font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] tabular-nums text-[var(--color-muted)]">
          {course.estimated_hours} h
        </span>
      </div>

      <p className="text-sm leading-relaxed text-[var(--color-ink-soft)]">{course.summary}</p>

      <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1.5 pt-2 font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--color-signal)]"
            aria-hidden="true"
          />
          {course.levels.join(" · ")}
        </span>
        <span className="tabular-nums">{plural(moduleCount, "module")}</span>
        <span className="tabular-nums">{plural(topicCount, "topic")}</span>
      </div>

      {topicCount > 0 ? (
        <details className="border-t border-[var(--color-rule-soft)] pt-3">
          <summary className="cursor-pointer list-none font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.12em] text-[var(--color-muted)] transition-colors hover:text-[var(--color-accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)]">
            <span className="select-none">
              Contents — {plural(topicCount, "topic")}
            </span>
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

function plural(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
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

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.16em] text-[var(--color-accent)]">
      {children}
    </span>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 bg-[var(--color-surface)] px-5 py-4">
      <dt className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.13em] text-[var(--color-muted)]">
        {label}
      </dt>
      <dd className="font-[family-name:var(--font-display)] text-2xl font-semibold tabular-nums">
        {value}
      </dd>
    </div>
  );
}
