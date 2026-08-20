import Link from "next/link";
import { getProjects } from "@/lib/api";

export const dynamic = "force-dynamic";
export const metadata = { title: "Projects" };

export default async function ProjectsPage() {
  const projects = await getProjects();

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-12">
      <header className="flex flex-col gap-2">
        <span className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.16em] text-[var(--color-accent)]">
          Projects
        </span>
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight text-balance">
          Work that spans topics
        </h1>
        <p className="prose-measure mt-2 text-sm text-[var(--color-ink-soft)]">
          A project takes several topics and makes you combine them on something real. Nothing here
          is marked by the platform — what these produce lives on your own machine, and the rubric
          is a structure for judging your own work honestly.
        </p>
      </header>

      <ol className="mt-10 flex flex-col gap-4">
        {projects.map((project) => (
          <li key={project.slug}>
            <article
              className={`rounded-sm border p-5 ${
                project.unlocked
                  ? "border-[var(--color-rule)] bg-[var(--color-surface)]"
                  : "border-[var(--color-rule-soft)]"
              }`}
            >
              <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.14em] text-[var(--color-accent)]">
                  {project.level}
                </span>
                <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.1em] text-[var(--color-muted)]">
                  ~{project.estimated_hours} hours
                </span>
                {!project.unlocked ? (
                  <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.1em] text-[var(--color-muted)]">
                    locked · {project.requires_topics.length} topics required
                  </span>
                ) : null}
              </div>

              <h2 className="mt-2 text-lg font-semibold">
                {project.unlocked ? (
                  <Link
                    href={`/projects/${project.slug}`}
                    className="hover:text-[var(--color-accent)]"
                  >
                    {project.title}
                  </Link>
                ) : (
                  project.title
                )}
              </h2>

              <p className="prose-measure mt-1 text-sm text-[var(--color-ink-soft)]">
                {project.summary}
              </p>
            </article>
          </li>
        ))}
      </ol>

      {projects.length === 0 ? (
        <p className="mt-10 text-sm text-[var(--color-muted)]">No projects yet.</p>
      ) : null}
    </div>
  );
}
