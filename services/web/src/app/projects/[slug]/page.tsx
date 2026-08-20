import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { SelfReview } from "@/components/SelfReview";
import { Markdown } from "@/content/Markdown";
import { getProject } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ProjectPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const project = await getProject(slug);

  // Null means no session: the lock state and the brief both depend on this
  // learner's progress, so there is nothing meaningful to show a stranger.
  if (project === null) redirect("/login");
  if (!project.slug) notFound();

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-12">
      <Link
        href="/projects"
        className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.14em] text-[var(--color-muted)] hover:text-[var(--color-accent)]"
      >
        ← Projects
      </Link>

      <header className="mt-4 flex flex-col gap-2">
        <div className="flex flex-wrap items-baseline gap-x-4">
          <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.14em] text-[var(--color-accent)]">
            {project.level}
          </span>
          <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.1em] text-[var(--color-muted)]">
            ~{project.estimated_hours} hours
          </span>
        </div>
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold leading-tight tracking-tight text-balance">
          {project.title}
        </h1>
        <p className="prose-measure text-[var(--color-ink-soft)]">{project.summary}</p>
      </header>

      {!project.unlocked ? (
        <section className="mt-8 rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] p-5">
          <h2 className="text-base font-semibold">Not yet</h2>
          <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
            This project combines things from several topics, and attempting it before those are
            finished teaches frustration rather than the subject. Still to complete:
          </p>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
            {project.missing_topics.map((title) => (
              <li key={title}>{title}</li>
            ))}
          </ul>
        </section>
      ) : (
        <>
          <div className="prose-measure mt-8">
            <Markdown body={project.brief} />
          </div>

          {project.constraints.length > 0 ? (
            <section className="mt-8">
              <h2 className="font-[family-name:var(--font-display)] text-xl font-semibold tracking-tight">
                Constraints
              </h2>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                These are what make it a project rather than a tutorial — each one removes an easy
                way out.
              </p>
              <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm">
                {project.constraints.map((constraint) => (
                  <li key={constraint}>{constraint}</li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="mt-8">
            <h2 className="font-[family-name:var(--font-display)] text-xl font-semibold tracking-tight">
              Deliverables
            </h2>
            <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm">
              {project.deliverables.map((deliverable) => (
                <li key={deliverable}>{deliverable}</li>
              ))}
            </ul>
          </section>

          <SelfReview slug={project.slug} rubric={project.rubric} />

          {project.going_further.length > 0 ? (
            <section className="mt-10 border-t border-[var(--color-rule)] pt-6">
              <h2 className="font-[family-name:var(--font-display)] text-xl font-semibold tracking-tight">
                Going further
              </h2>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                After the work is finished, not instead of finishing it.
              </p>
              <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-[var(--color-ink-soft)]">
                {project.going_further.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
