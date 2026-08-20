import type { Metadata } from "next";
import Link from "next/link";
import { search } from "@/lib/api";

export const metadata: Metadata = { title: "Search" };

const TYPES = [
  { value: "", label: "Everything" },
  { value: "lesson", label: "Lessons" },
  { value: "lab", label: "Labs" },
  { value: "troubleshooting", label: "Troubleshooting" },
  { value: "glossary", label: "Glossary" },
  { value: "topic", label: "Topics" },
];

const TYPE_LABELS: Record<string, string> = {
  topic: "topic",
  lesson: "lesson",
  lab: "lab",
  troubleshooting: "scenario",
  glossary: "term",
  exercise: "exercise",
  interview: "interview",
  assessment: "assessment",
  quiz: "quiz",
};

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; type?: string }>;
}) {
  const params = await searchParams;
  const query = (params.q ?? "").trim();
  const type = params.type ?? "";

  const results = query.length >= 2 ? await search(query, type || undefined) : null;

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight">
        {query ? `Results for “${query}”` : "Search"}
      </h1>

      {results ? (
        <p className="mt-2 font-[family-name:var(--font-mono)] text-[0.68rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
          {results.total} {results.total === 1 ? "result" : "results"}
        </p>
      ) : (
        <p className="mt-2 text-sm text-[var(--color-muted)]">
          Search lessons, labs, troubleshooting scenarios and the glossary. Two characters minimum.
        </p>
      )}

      {query ? (
        <nav className="mt-6 flex flex-wrap gap-2">
          {TYPES.map((option) => {
            const active = option.value === type;
            return (
              <Link
                key={option.value || "all"}
                href={`/search?q=${encodeURIComponent(query)}${
                  option.value ? `&type=${option.value}` : ""
                }`}
                className={`rounded-sm border px-3 py-1 font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.1em] ${
                  active
                    ? "border-[var(--color-accent)] text-[var(--color-accent)]"
                    : "border-[var(--color-rule)] text-[var(--color-muted)] hover:border-[var(--color-accent)]"
                }`}
              >
                {option.label}
              </Link>
            );
          })}
        </nav>
      ) : null}

      {results && results.hits.length === 0 ? (
        <p className="mt-10 rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] px-4 py-6 text-sm text-[var(--color-muted)]">
          Nothing matched. Try a single distinctive word — <code>EPERM</code>, <code>zombie</code>,{" "}
          <code>vdso</code> — rather than a whole sentence.
        </p>
      ) : null}

      <ol className="mt-8 flex flex-col gap-6">
        {results?.hits.map((hit) => (
          <li key={`${hit.entity_type}-${hit.url}-${hit.title}`}>
            <Link href={hit.url} className="group block">
              <div className="flex items-baseline gap-3">
                <span className="font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.14em] text-[var(--color-accent)]">
                  {TYPE_LABELS[hit.entity_type] ?? hit.entity_type}
                </span>
                {hit.topic_title && hit.entity_type !== "topic" ? (
                  <span className="truncate font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.1em] text-[var(--color-muted)]">
                    {hit.topic_title}
                  </span>
                ) : null}
              </div>

              <h2 className="mt-1 text-base font-semibold group-hover:text-[var(--color-accent)]">
                {hit.title}
              </h2>

              {hit.snippet ? (
                // The snippet contains <mark> tags from ts_headline. The corpus
                // is curriculum prose from git — never user-submitted text — so
                // there is nothing here that a learner could have authored.
                <p
                  className="mt-1 text-sm leading-relaxed text-[var(--color-ink-soft)] [&_mark]:bg-transparent [&_mark]:font-semibold [&_mark]:text-[var(--color-accent)]"
                  // biome-ignore lint/security/noDangerouslySetInnerHtml: server-rendered highlight markup over git-authored content
                  dangerouslySetInnerHTML={{ __html: hit.snippet }}
                />
              ) : null}
            </Link>
          </li>
        ))}
      </ol>
    </div>
  );
}
