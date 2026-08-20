import Link from "next/link";
import { redirect } from "next/navigation";
import { getDashboard, getMyAchievements } from "@/lib/api";

export const dynamic = "force-dynamic";
export const metadata = { title: "Dashboard" };

export default async function DashboardPage() {
  const [data, achievements] = await Promise.all([getDashboard(), getMyAchievements()]);
  if (!data) redirect("/login");

  const { totals } = data;
  const percent = totals.topics_total
    ? Math.round((100 * totals.topics_completed) / totals.topics_total)
    : 0;

  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-12 flex flex-col gap-10">
      <header className="flex flex-col gap-2">
        <span className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.16em] text-[var(--color-accent)]">
          Dashboard
        </span>
        <h1 className="font-[family-name:var(--font-display)] text-4xl font-semibold tracking-tight">
          {data.display_name}
        </h1>
      </header>

      <div className="flex flex-wrap gap-x-10 gap-y-3 border-y border-[var(--color-rule)] py-4">
        <Stat
          label="Topics completed"
          value={`${totals.topics_completed}/${totals.topics_total}`}
        />
        <Stat label="Curriculum" value={`${percent}%`} />
        <Stat label="Quizzes passed" value={String(totals.quizzes_passed)} />
      </div>

      {data.next_topic ? (
        <section className="rounded-sm border border-[var(--color-accent)] bg-[var(--color-surface)] p-5">
          <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.14em] text-[var(--color-accent)]">
            Pick up here
          </span>
          <Link
            href={`/topics/${data.next_topic.slug}`}
            className="mt-2 block font-[family-name:var(--font-display)] text-xl font-semibold tracking-tight hover:text-[var(--color-accent)]"
          >
            {data.next_topic.title}
          </Link>
          <span className="font-[family-name:var(--font-mono)] text-[0.66rem] text-[var(--color-muted)]">
            {data.next_topic.course} · {data.next_topic.estimated_minutes} min
          </span>
        </section>
      ) : (
        <p className="text-sm text-[var(--color-muted)]">
          Everything written so far is complete. More topics are on the way.
        </p>
      )}

      {achievements && achievements.length > 0 ? (
        <section className="flex flex-col gap-3">
          <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight">
            Earned
          </h2>
          <ul className="grid gap-3 sm:grid-cols-2">
            {achievements.map((achievement) => (
              <li
                key={`${achievement.code}-${achievement.scope}`}
                className="rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] p-4"
              >
                <span className="font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.14em] text-[var(--color-signal)]">
                  {achievement.code}
                </span>
                <p className="mt-1 text-sm font-semibold">{achievement.title}</p>
                {/* The evidence, not a slogan: an achievement whose detail says
                    nothing is indistinguishable from participation. */}
                <p className="mt-0.5 text-xs text-[var(--color-muted)]">{achievement.detail}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {data.weak_objectives.length > 0 ? (
        <section className="flex flex-col gap-3">
          <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight">
            Where you are weakest
          </h2>
          <p className="prose-measure text-sm text-[var(--color-muted)]">
            Ranked by evidence, not by how recently you saw them. Proficiency is your weakest
            objective, not your average.
          </p>
          <ul className="border-t border-[var(--color-rule)]">
            {data.weak_objectives.map((objective) => (
              <li
                key={objective.code}
                className="flex flex-col gap-1 border-b border-[var(--color-rule-soft)] py-3"
              >
                <span className="font-[family-name:var(--font-mono)] text-[0.66rem] text-[var(--color-accent)]">
                  {objective.code}
                </span>
                <span className="text-sm text-[var(--color-ink-soft)]">{objective.statement}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {data.recent_attempts.length > 0 ? (
        <section className="flex flex-col gap-3">
          <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight">
            Recent quiz attempts
          </h2>
          <ul className="border-t border-[var(--color-rule)]">
            {data.recent_attempts.map((attempt) => (
              <li
                key={attempt.submitted_at}
                className="flex items-baseline justify-between border-b border-[var(--color-rule-soft)] py-2.5"
              >
                <span className="font-[family-name:var(--font-mono)] text-sm tabular-nums">
                  {attempt.score}%
                </span>
                <span
                  className={`font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.12em] ${
                    attempt.passed ? "text-[var(--color-signal)]" : "text-[var(--color-muted)]"
                  }`}
                >
                  {attempt.passed ? "passed" : "not yet"}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <TopicList title="In progress" topics={data.in_progress} />
      <TopicList title="Completed" topics={data.completed} />
      <TopicList title="Available next" topics={data.available} />
    </div>
  );
}

function TopicList({
  title,
  topics,
}: {
  title: string;
  topics: { slug: string; title: string; course: string; estimated_minutes: number }[];
}) {
  if (topics.length === 0) return null;
  return (
    <section className="flex flex-col gap-3">
      <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight">
        {title}
      </h2>
      <ul className="border-t border-[var(--color-rule)]">
        {topics.map((topic) => (
          <li key={topic.slug}>
            <Link
              href={`/topics/${topic.slug}`}
              className="flex items-baseline justify-between gap-4 border-b border-[var(--color-rule-soft)] py-2.5 hover:text-[var(--color-accent)]"
            >
              <span className="text-[0.95rem]">{topic.title}</span>
              <span className="shrink-0 font-[family-name:var(--font-mono)] text-[0.66rem] tabular-nums text-[var(--color-muted)]">
                {topic.estimated_minutes} min
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
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
