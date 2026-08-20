import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { LabTerminal } from "@/components/LabTerminal";
import { StepFooter } from "@/components/player/StepFooter";
import { Quiz } from "@/components/Quiz";
import { Troubleshooting } from "@/components/Troubleshooting";
import { Markdown } from "@/content/Markdown";
import {
  ApiError,
  getAssessment,
  getExercises,
  getInterview,
  getLab,
  getMyProgress,
  getOutline,
  getQuiz,
  getScenarios,
  getTopic,
} from "@/lib/api";
import { isSignedIn } from "@/lib/session";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ topic: string; step: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { topic, step } = await params;
  try {
    const outline = await getOutline(topic);
    const current = outline.steps.find((s) => s.slug === step);
    return { title: current ? `${current.title} · ${outline.topic_title}` : outline.topic_title };
  } catch {
    return { title: "Learn" };
  }
}

export default async function StepPage({ params }: Props) {
  const { topic, step } = await params;

  let outline: Awaited<ReturnType<typeof getOutline>>;
  try {
    outline = await getOutline(topic);
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 404) notFound();
    throw cause;
  }

  const index = outline.steps.findIndex((s) => s.slug === step);
  if (index === -1) notFound();

  const current = outline.steps[index];
  if (!current) notFound();

  const [signedIn, progress] = await Promise.all([isSignedIn(), getMyProgress()]);
  const done = (progress ?? []).some(
    (row) => row.entity_id === current.entity_id && row.status === "completed",
  );

  return (
    <div className="flex min-h-[calc(100dvh-5rem)] flex-col">
      <div className="flex-1">
        <StepHeader kind={current.kind} title={current.title} subtitle={current.subtitle} />
        <StepBody topicSlug={topic} step={current} />
      </div>

      <StepFooter
        topicSlug={topic}
        step={current}
        previous={outline.steps[index - 1] ?? null}
        next={outline.steps[index + 1] ?? null}
        index={index}
        total={outline.steps.length}
        initiallyDone={done}
        signedIn={signedIn}
      />
    </div>
  );
}

const KIND_LABEL: Record<string, string> = {
  lesson: "Read",
  lab: "Hands-on lab",
  exercise: "Exercises",
  troubleshooting: "Diagnose",
  quiz: "Quiz",
  assessment: "Assessment",
  interview: "Interview preparation",
};

function StepHeader({
  kind,
  title,
  subtitle,
}: {
  kind: string;
  title: string;
  subtitle: string | null;
}) {
  // Labs render their own header — the terminal needs the vertical space.
  if (kind === "lab") return null;
  return (
    <header className="mb-7 flex flex-col gap-2">
      <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.16em] text-[var(--color-accent)]">
        {KIND_LABEL[kind] ?? kind}
        {subtitle && kind !== "lesson" ? ` · ${subtitle}` : ""}
      </span>
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold leading-tight tracking-tight text-balance">
        {title}
      </h1>
    </header>
  );
}

async function StepBody({
  topicSlug,
  step,
}: {
  topicSlug: string;
  step: Awaited<ReturnType<typeof getOutline>>["steps"][number];
}) {
  switch (step.kind) {
    case "lesson": {
      const detail = await getTopic(topicSlug);
      const section = step.slug.replace(/^read-/, "");
      const lesson = detail.lessons.find((item) => item.section === section);
      if (!lesson) notFound();
      return (
        <div className="prose-measure">
          <Markdown body={lesson.body_md} topicSlug={topicSlug} />
        </div>
      );
    }

    case "lab": {
      const lab = await getLab(topicSlug, step.slug.replace(/^lab-/, ""));
      if (lab.tier > 2) {
        return (
          <p className="prose-measure rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-ink-soft)]">
            This lab needs isolation tier {lab.tier} — nested containers, which require a Linux host
            running Sysbox. Run the steps on your own machine for now; the instructions and checks
            are identical.
          </p>
        );
      }
      return (
        <LabTerminal
          topicSlug={topicSlug}
          labSlug={lab.slug}
          title={lab.title}
          intro={lab.intro}
          steps={lab.steps as { id: string; instruction: string; hint: string | null }[]}
          durationMinutes={lab.duration_minutes}
        />
      );
    }

    case "troubleshooting": {
      const scenarios = await getScenarios(topicSlug);
      const code = step.slug.replace(/^diagnose-/, "");
      const scenario = scenarios.find((item) => item.id.endsWith(code));
      if (!scenario) notFound();
      return <Troubleshooting topicSlug={topicSlug} scenario={scenario} />;
    }

    case "quiz": {
      const paper = await getQuiz(topicSlug);
      return (
        <div className="max-w-3xl">
          <p className="mb-7 text-sm text-[var(--color-ink-soft)]">
            {paper.question_count} questions, pass at {paper.pass_score}%. Every option is explained
            once you submit — including the ones you did not choose.
          </p>
          <Quiz paper={paper} />
        </div>
      );
    }

    case "exercise": {
      const exercises = await getExercises(topicSlug);
      return (
        <div className="prose-measure flex flex-col gap-8">
          <p className="text-sm text-[var(--color-muted)]">
            Work these on paper or in a shell. They are not graded — they are here because producing
            an answer is a different act from recognising one.
          </p>
          {exercises.map((exercise, position) => (
            <section key={exercise.id} className="flex flex-col gap-2">
              <div className="flex items-baseline gap-3">
                <span className="font-[family-name:var(--font-mono)] text-[0.66rem] tabular-nums text-[var(--color-muted)]">
                  {String(position + 1).padStart(2, "0")}
                </span>
                <h2 className="font-[family-name:var(--font-display)] text-xl font-semibold tracking-tight">
                  {exercise.title}
                </h2>
                <span className="font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.12em] text-[var(--color-signal)]">
                  {exercise.level}
                </span>
              </div>
              <div className="text-sm">
                <Markdown body={exercise.prompt} />
              </div>
            </section>
          ))}
        </div>
      );
    }

    case "interview": {
      const questions = await getInterview(topicSlug);
      return (
        <div className="prose-measure flex flex-col gap-6">
          <p className="text-sm text-[var(--color-muted)]">
            Ordered from beginner to architect. Answer out loud before reading on — the gap between
            knowing something and being able to say it is the thing interviews test.
          </p>
          <ol className="flex flex-col gap-5 border-t border-[var(--color-rule)]">
            {questions.map((question) => (
              <li key={question.id} className="flex flex-col gap-2 pt-4">
                <span className="font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.12em] text-[var(--color-signal)]">
                  {question.level}
                </span>
                <p className="font-medium">{question.question}</p>
                {question.follow_ups.length > 0 ? (
                  <ul className="list-disc pl-5 text-sm text-[var(--color-muted)]">
                    {question.follow_ups.map((followUp) => (
                      <li key={followUp}>{followUp}</li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ol>
        </div>
      );
    }

    case "assessment": {
      const parts = await getAssessment(topicSlug);
      return (
        <div className="prose-measure flex flex-col gap-8">
          <p className="text-sm text-[var(--color-muted)]">
            Three parts, all required. A passed quiz does not make you proficient — this does, and
            it is graded against a rubric rather than a key.
          </p>
          {parts.map((part) => (
            <section key={part.id} className="flex flex-col gap-2">
              <div className="flex items-baseline gap-3">
                <span className="font-[family-name:var(--font-mono)] text-sm font-semibold text-[var(--color-accent)]">
                  {part.id}
                </span>
                <h2 className="font-[family-name:var(--font-display)] text-xl font-semibold tracking-tight">
                  {part.title}
                </h2>
                <span className="font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
                  {part.kind}
                </span>
              </div>
              <div className="text-sm">
                <Markdown body={part.prompt} />
              </div>
            </section>
          ))}
        </div>
      );
    }

    default:
      return <p className="text-sm text-[var(--color-muted)]">Nothing to show here yet.</p>;
  }
}
