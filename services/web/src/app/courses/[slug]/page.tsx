import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError, type CourseDetail, getCourse } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function CoursePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;

  let course: CourseDetail;
  try {
    course = await getCourse(slug);
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 404) notFound();
    throw cause;
  }

  const topics = course.modules.flatMap((m) => m.topics);
  const minutes = topics.reduce((sum, t) => sum + t.estimated_minutes, 0);
  const firstTopic = topics[0] ?? null;

  return (
    <div className="flex flex-col">
      <section className="border-b border-[var(--color-rule)] bg-[var(--color-surface)]">
        <div className="mx-auto w-full max-w-4xl px-6 py-12">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.13em] text-[var(--color-muted)] transition-colors hover:text-[var(--color-accent)]"
          >
            <span aria-hidden="true">←</span> All courses
          </Link>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <span className="font-[family-name:var(--font-mono)] text-[0.72rem] font-semibold tracking-[0.08em] text-[var(--color-accent)]">
              {course.code}
            </span>
            <span className="rounded border border-[var(--color-rule-soft)] px-1.5 py-0.5 font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] text-[var(--color-signal)]">
              {course.levels.join(" ")}
            </span>
            <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
              {course.track}
            </span>
          </div>

          <h1 className="mt-3 font-[family-name:var(--font-display)] text-[clamp(2rem,4.5vw,3rem)] font-semibold leading-[1.05] tracking-tight text-balance">
            {course.title}
          </h1>

          <p className="prose-measure mt-4 text-[1.05rem] leading-relaxed text-[var(--color-ink-soft)]">
            {course.summary}
          </p>

          <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2 font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.12em] tabular-nums text-[var(--color-muted)]">
            <span>{plural(course.modules.length, "module")}</span>
            <span>{plural(topics.length, "topic")}</span>
            <span>{course.estimated_hours} h estimated</span>
            <span>{minutes} min of material</span>
          </div>

          {firstTopic ? (
            <Link
              href={`/topics/${firstTopic.slug}`}
              className="mt-7 inline-flex items-center gap-2 rounded-full bg-[var(--color-accent)] px-5 py-2.5 text-sm font-semibold text-[var(--color-surface)] transition-opacity hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)]"
            >
              Start the first topic
              <span aria-hidden="true">→</span>
            </Link>
          ) : null}
        </div>
      </section>

      <div className="mx-auto w-full max-w-4xl px-6 py-12 flex flex-col gap-10">
        {course.modules.map((module, moduleIndex) => (
          <section key={module.slug} className="flex flex-col gap-4">
            <div className="flex items-baseline gap-3">
              <span className="font-[family-name:var(--font-mono)] text-[0.7rem] tabular-nums text-[var(--color-accent)]">
                {String(moduleIndex + 1).padStart(2, "0")}
              </span>
              <h2 className="font-[family-name:var(--font-display)] text-[1.4rem] font-semibold tracking-tight">
                {module.title}
              </h2>
              <span className="h-px flex-1 bg-[var(--color-rule)]" aria-hidden="true" />
            </div>

            {module.summary ? (
              <p className="prose-measure -mt-1 pl-8 text-sm leading-relaxed text-[var(--color-ink-soft)]">
                {module.summary}
              </p>
            ) : null}

            <ul className="flex flex-col gap-3 pl-8">
              {module.topics.map((topic) => (
                <li key={topic.slug}>
                  <Link
                    href={`/topics/${topic.slug}`}
                    className="group flex flex-col gap-1.5 rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-4 transition-all duration-200 hover:border-[var(--color-accent)] hover:shadow-md hover:shadow-black/5"
                  >
                    <div className="flex items-baseline justify-between gap-4">
                      <h3 className="font-[family-name:var(--font-display)] text-[1.05rem] font-semibold leading-snug tracking-tight transition-colors group-hover:text-[var(--color-accent)]">
                        {topic.title}
                      </h3>
                      <span className="shrink-0 font-[family-name:var(--font-mono)] text-[0.62rem] tabular-nums text-[var(--color-muted)]">
                        {topic.estimated_minutes} min
                      </span>
                    </div>
                    {topic.summary ? (
                      <p className="text-[0.86rem] leading-relaxed text-[var(--color-ink-soft)]">
                        {topic.summary}
                      </p>
                    ) : null}
                    <div className="mt-0.5 flex flex-wrap items-center gap-2 font-[family-name:var(--font-mono)] text-[0.58rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
                      <span className="text-[var(--color-signal)]">{topic.levels.join(" ")}</span>
                      {topic.tags.slice(0, 3).map((tag) => (
                        <span
                          key={tag}
                          className="rounded bg-[var(--color-surface-2)] px-1.5 py-0.5"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

function plural(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}
