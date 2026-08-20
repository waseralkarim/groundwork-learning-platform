import Link from "next/link";
import type { Inventory, InventoryTopic, LintReport } from "@/lib/api";
import { ApiError, getInventory, getLintReport } from "@/lib/api";
import { sessionHeader } from "@/lib/session";

export const dynamic = "force-dynamic";
export const metadata = { title: "Authoring" };

/**
 * The authoring view.
 *
 * Every topic in this platform was written by editing files in a checkout and
 * running the CLI in a container. That still works, and it means an author
 * needs a clone, Docker and the command before they can find out whether what
 * they wrote is valid.
 *
 * This page closes the feedback half of that gap. It does not write content:
 * curriculum stays in files under version control, because that is what keeps
 * it reviewable, versioned and checkable by the linter and the lab walker. What
 * was missing was a way to *see* the state of it without a terminal.
 */

function StatusPill({
  children,
  tone,
}: {
  children: React.ReactNode;
  tone: "ok" | "warn" | "bad";
}) {
  const tones = {
    ok: "border-[var(--color-rule)] text-[var(--color-muted)]",
    warn: "border-[var(--color-accent)] text-[var(--color-accent)]",
    bad: "border-[var(--color-danger,#b4433a)] text-[var(--color-danger,#b4433a)]",
  } as const;
  return (
    <span
      className={`rounded-sm border px-1.5 py-0.5 font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.1em] ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

function TopicRow({ topic }: { topic: InventoryTopic }) {
  const { done } = topic;
  const counts = [
    "lessons",
    "labs",
    "quiz",
    "troubleshooting",
    "exercises",
    "interview",
    "assessment",
  ];

  return (
    <li className="border-t border-[var(--color-rule-soft)] py-3 first:border-t-0">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <Link
          href={`/topics/${topic.slug}`}
          className="font-medium text-[var(--color-ink)] underline decoration-[var(--color-rule)] underline-offset-4 hover:decoration-[var(--color-accent)]"
        >
          {topic.title}
        </Link>
        <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] text-[var(--color-accent)]">
          {topic.levels.join(" ")}
        </span>
        {topic.status !== "published" ? <StatusPill tone="warn">{topic.status}</StatusPill> : null}
        {done.blocking ? (
          <StatusPill tone="bad">missing {done.missing.join(", ")}</StatusPill>
        ) : done.warnings.length > 0 ? (
          <StatusPill tone="warn">no {done.warnings.join(", ")}</StatusPill>
        ) : (
          <StatusPill tone="ok">complete</StatusPill>
        )}
      </div>

      <dl className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 font-[family-name:var(--font-mono)] text-[0.66rem] text-[var(--color-muted)]">
        {counts.map((key) => (
          <div key={key} className="flex gap-1">
            <dt>{key}</dt>
            <dd className={done.present[key] ? "text-[var(--color-ink-soft)]" : "opacity-40"}>
              {done.present[key] ?? 0}
            </dd>
          </div>
        ))}
        <div className="flex gap-1">
          <dt>objectives</dt>
          <dd className="text-[var(--color-ink-soft)]">{topic.objectives}</dd>
        </div>
      </dl>
    </li>
  );
}

function Findings({ report }: { report: LintReport }) {
  if (report.ok && report.warnings.length === 0) {
    return (
      <p className="text-sm text-[var(--color-ink-soft)]">
        No parse errors, no lint errors, no warnings. This is the same check{" "}
        <code className="font-[family-name:var(--font-mono)] text-[0.8em]">content lint</code> runs.
      </p>
    );
  }

  const groups: [string, { where: string; message: string; rule?: string }[]][] = [
    ["Parse errors", report.parse_errors],
    ["Errors", report.errors],
    ["Warnings", report.warnings],
  ];

  return (
    <div className="flex flex-col gap-5">
      {groups.map(([label, items]) =>
        items.length === 0 ? null : (
          <section key={label}>
            <h3 className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.14em] text-[var(--color-accent)]">
              {label} ({items.length})
            </h3>
            <ul className="mt-2 flex flex-col gap-1.5">
              {items.map((item) => (
                <li
                  key={`${label}-${item.rule ?? ""}-${item.where}-${item.message}`}
                  className="font-[family-name:var(--font-mono)] text-[0.72rem] leading-relaxed"
                >
                  {item.rule ? (
                    <span className="text-[var(--color-accent)]">[{item.rule}] </span>
                  ) : null}
                  <span className="text-[var(--color-ink-soft)]">{item.where}</span>
                  <span className="text-[var(--color-muted)]"> — {item.message}</span>
                </li>
              ))}
            </ul>
          </section>
        ),
      )}
      {report.parse_errors.length > 0 ? (
        <p className="prose-measure text-sm text-[var(--color-ink-soft)]">
          Read the parse errors first. A file that could not be read at all makes everything
          referencing it show up as missing, so the rest of this list is mostly symptoms.
        </p>
      ) : null}
    </div>
  );
}

export default async function AuthoringPage() {
  const headers = await sessionHeader();

  let inventory: Inventory;
  let report: LintReport;

  try {
    [inventory, report] = await Promise.all([getInventory(headers), getLintReport(headers)]);
  } catch (error) {
    const status = error instanceof ApiError ? error.status : undefined;
    return (
      <div className="mx-auto w-full max-w-2xl px-6 py-16">
        <h1 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight">
          {status === 401 ? "Sign in to continue" : "Administrator access required"}
        </h1>
        <p className="prose-measure mt-3 text-sm text-[var(--color-ink-soft)]">
          {status === 401
            ? "This view is part of the authoring tools and needs an account."
            : "This view reads the content tree and can trigger a re-ingest, so it is limited to administrators. The first account registered on a fresh install becomes one."}
        </p>
        <Link
          href="/"
          className="mt-6 inline-block text-sm underline decoration-[var(--color-rule)] underline-offset-4 hover:decoration-[var(--color-accent)]"
        >
          Back to the curriculum
        </Link>
      </div>
    );
  }

  const t = inventory.totals;

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-12">
      <header className="flex flex-col gap-2">
        <span className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.16em] text-[var(--color-accent)]">
          Authoring
        </span>
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight text-balance">
          What exists, and what is not finished
        </h1>
        <p className="prose-measure mt-2 text-sm text-[var(--color-ink-soft)]">
          Content lives in files under version control — that is what keeps it reviewable and lets
          the linter and the lab walker check it. This view does not edit anything. It reads the
          same tree the CLI reads, so you can see the state of the curriculum and what the linter
          says without a terminal.
        </p>
      </header>

      <section className="mt-10">
        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-sm border border-[var(--color-rule)] bg-[var(--color-rule-soft)] sm:grid-cols-4">
          {[
            ["courses", t.courses],
            ["modules", t.modules],
            ["topics", t.topics],
            ["lessons", t.lessons],
            ["labs", t.labs],
            ["projects", t.projects],
            ["incomplete", t.incomplete],
            ["lint", report.counts.errors + report.counts.parse_errors],
          ].map(([label, value]) => (
            <div key={String(label)} className="bg-[var(--color-surface)] px-4 py-3">
              <dt className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
                {label === "lint" ? "lint errors" : label}
              </dt>
              <dd
                className={`mt-0.5 font-[family-name:var(--font-display)] text-2xl font-semibold tabular-nums ${
                  (label === "incomplete" || label === "lint") && Number(value) > 0
                    ? "text-[var(--color-danger,#b4433a)]"
                    : "text-[var(--color-ink)]"
                }`}
              >
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="mt-12">
        <h2 className="font-[family-name:var(--font-display)] text-xl font-semibold tracking-tight">
          Checks
        </h2>
        <div className="mt-4">
          <Findings report={report} />
        </div>
      </section>

      <section className="mt-12">
        <h2 className="font-[family-name:var(--font-display)] text-xl font-semibold tracking-tight">
          Curriculum
        </h2>
        <p className="prose-measure mt-2 text-sm text-[var(--color-ink-soft)]">
          A topic is complete when it has lessons, a quiz, an assessment and a lab — plus a
          troubleshooting scenario once it claims L3. Exercises and interview questions are
          recommended rather than required, so their absence is a warning.
        </p>

        <div className="mt-6 flex flex-col gap-8">
          {inventory.courses.map((course) => (
            <article key={course.id}>
              <h3 className="flex flex-wrap items-baseline gap-x-3">
                <span className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.14em] text-[var(--color-accent)]">
                  {course.code}
                </span>
                <span className="font-[family-name:var(--font-display)] text-lg font-semibold tracking-tight">
                  {course.title}
                </span>
              </h3>

              <div className="mt-3 flex flex-col gap-5">
                {course.modules.map((module) => (
                  <div key={module.id}>
                    <h4 className="font-[family-name:var(--font-mono)] text-[0.68rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
                      {module.title}
                    </h4>
                    <ul className="mt-1">
                      {module.topics.map((topic) => (
                        <TopicRow key={topic.id} topic={topic} />
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="mt-14 rounded-sm border border-[var(--color-rule-soft)] p-5">
        <h2 className="font-[family-name:var(--font-display)] text-lg font-semibold tracking-tight">
          Publishing a change
        </h2>
        <p className="prose-measure mt-2 text-sm text-[var(--color-ink-soft)]">
          Edit the files, then re-ingest so the database matches. Ingest refuses invalid content, so
          it cannot put the platform into a state the linter would have rejected, and it is
          idempotent — content keys are derived from content ids, so running it twice changes
          nothing.
        </p>
        <pre className="mt-4 overflow-x-auto rounded-sm bg-[var(--color-surface-sunk,var(--color-surface))] p-3 font-[family-name:var(--font-mono)] text-[0.72rem] leading-relaxed">
          <code>
            {`docker compose exec api python -m app.content.cli lint
docker compose exec api python -m app.content.cli ingest

# or, as an administrator, from any client that sends an Origin header:
curl -X POST -b "$COOKIES" -H "Origin: $BASE" "$BASE/api/v1/authoring/ingest"`}
          </code>
        </pre>
        <p className="prose-measure mt-3 text-sm text-[var(--color-ink-soft)]">
          Labs need one more step that no API can do for you:{" "}
          <code className="font-[family-name:var(--font-mono)] text-[0.85em]">task labs:walk</code>{" "}
          runs every lab as a learner and asserts its own checks pass. A lab that parses is not a
          lab that teaches.
        </p>
      </section>
    </div>
  );
}
