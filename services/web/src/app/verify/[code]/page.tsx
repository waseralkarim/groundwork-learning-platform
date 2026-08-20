import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { verifyCertificate } from "@/lib/api";

export const metadata: Metadata = { title: "Verify a certificate" };

/**
 * Public certificate verification.
 *
 * No account, no session, no sign-in wall. Someone holding the code — a hiring
 * manager, a colleague — can check it, which is the only thing that makes the
 * certificate worth anything.
 *
 * The page states what the credential required, not just that it exists. "Passed
 * a course" means nothing without knowing what passing took.
 */
export default async function VerifyPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;

  const certificate = await verifyCertificate(code).catch(() => null);
  if (!certificate) notFound();

  const issued = new Date(certificate.issued_at).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <div className="rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] p-8">
        <div className="flex items-baseline gap-3">
          <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.16em] text-[var(--color-signal)]">
            Verified
          </span>
          <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
            {certificate.course_code}
          </span>
        </div>

        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight text-balance">
          {certificate.holder_name}
        </h1>
        <p className="mt-1 text-lg text-[var(--color-ink-soft)]">{certificate.course_title}</p>

        <dl className="mt-8 grid gap-x-8 gap-y-4 sm:grid-cols-2">
          <div>
            <dt className="font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
              Issued
            </dt>
            <dd className="mt-0.5 text-sm">{issued}</dd>
          </div>
          <div>
            <dt className="font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
              Topics completed
            </dt>
            <dd className="mt-0.5 text-sm tabular-nums">{certificate.topics_completed}</dd>
          </div>
          <div>
            <dt className="font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
              Weakest objective
            </dt>
            <dd className="mt-0.5 text-sm tabular-nums">
              {certificate.weakest_objective_score}/100
            </dd>
          </div>
          <div>
            <dt className="font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
              Code
            </dt>
            <dd className="mt-0.5 font-[family-name:var(--font-mono)] text-sm">
              {certificate.code}
            </dd>
          </div>
        </dl>
      </div>

      <section className="mt-8 border-l-2 border-[var(--color-rule)] pl-4 text-sm text-[var(--color-muted)]">
        <h2 className="mb-2 font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.14em] text-[var(--color-ink-soft)]">
          What this required
        </h2>
        <p className="mb-3 leading-relaxed">
          Every learning objective in every topic of this course had to be demonstrated — not
          visited, demonstrated. Each objective is scored against the evidence it offers, weighted
          by how hard that evidence is to fake: a quiz answer counts for least, a verified lab and a
          troubleshooting diagnosis for most.
        </p>
        <p className="leading-relaxed">
          The score above is the <strong>weakest</strong> objective, not the average, and
          proficiency requires evidence beyond multiple choice. Passing the quizzes alone does not
          produce this certificate.
        </p>
      </section>
    </div>
  );
}
