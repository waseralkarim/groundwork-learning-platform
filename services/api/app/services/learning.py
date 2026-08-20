"""Progress, grading and gating.

The rules that make this platform trustworthy live here:

- **Grading happens on the server.** The browser never receives an answer key,
  so it cannot grade, and a forged submission cannot claim a score.
- **The solution is gated behind an attempt.** A troubleshooting scenario with
  `reveal_policy: progressive` will not surrender its root cause until the
  learner has committed to a diagnosis. Handing over the answer on request is
  what makes most troubleshooting content worthless.
- **Proficiency is the weakest objective, not the average.** You are as strong
  as your weakest objective; averaging lets a learner ace the easy half and
  believe they are done.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.core.metrics import record_quiz_attempt, record_topic_status
from app.models.content import ContentVersion
from app.models.curriculum import (
    Course,
    Module,
    Objective,
    Prerequisite,
    Quiz,
    QuizQuestion,
    Topic,
    TopicItem,
)
from app.models.identity import Hypothesis, QuizAnswer, QuizAttempt, User, UserProgress
from app.services.jobs import evaluate_achievements_for

log = get_logger(__name__)

ENTITY_TYPES = frozenset(
    {
        "topic",
        "lesson",
        "lab",
        "exercise",
        "quiz",
        "troubleshooting",
        "interview",
        "assessment",
        "project",
        "course",
    }
)
STATUSES = frozenset({"not_started", "in_progress", "completed", "failed"})

# Weights for the competence model. A quiz answer is weak evidence; diagnosing a
# broken system is strong evidence. See docs/architecture/05-data-model.md §5.5.
EVIDENCE_WEIGHT = {
    "quiz": 1,
    "exercise": 2,
    "lab": 3,
    "troubleshooting": 4,
    "assessment": 4,
}


class LearningError(Exception):
    pass


class NotFoundError(LearningError):
    pass


class LockedError(LearningError):
    """A prerequisite has not been met, or a reveal has not been earned."""


# ------------------------------------------------------------------- progress


async def set_progress(
    db: AsyncSession,
    user: User,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    status: str,
    score: float | None = None,
) -> UserProgress:
    if entity_type not in ENTITY_TYPES:
        raise LearningError(f"unknown entity type '{entity_type}'")
    if status not in STATUSES:
        raise LearningError(f"unknown status '{status}'")

    now = datetime.now(UTC)
    row = await db.scalar(
        select(UserProgress).where(
            UserProgress.user_id == user.id,
            UserProgress.entity_type == entity_type,
            UserProgress.entity_id == entity_id,
        )
    )

    if row is None:
        row = UserProgress(
            user_id=user.id,
            entity_type=entity_type,
            entity_id=entity_id,
            status=status,
            score=score,
            attempts=0,
            first_seen_at=now,
        )
        db.add(row)
    else:
        # Completion is not revoked by revisiting. Re-reading a finished lesson
        # should not quietly reset it to in_progress.
        if not (row.status == "completed" and status == "in_progress"):
            row.status = status
        if score is not None:
            row.score = max(score, row.score or 0)

    if status == "completed" and row.completed_at is None:
        row.completed_at = now

    await db.commit()

    # The learning funnel. Topic-level only: an entity_type of "lesson" would
    # bury the signal that matters under fifteen times the volume.
    if entity_type == "topic":
        record_topic_status(status, str(entity_id))

    # Completing something may have earned an achievement. Evaluated in the
    # worker, so the size of the curriculum never shows up in this response.
    if status == "completed":
        await evaluate_achievements_for(user.id)

    return row


async def progress_map(db: AsyncSession, user: User) -> dict[tuple[str, uuid.UUID], UserProgress]:
    rows = await db.scalars(select(UserProgress).where(UserProgress.user_id == user.id))
    return {(row.entity_type, row.entity_id): row for row in rows}


# --------------------------------------------------------------- prerequisites


@dataclass
class GateResult:
    unlocked: bool
    missing: list[dict]

    @property
    def reason(self) -> str | None:
        if self.unlocked:
            return None
        names = ", ".join(item["title"] for item in self.missing)
        return f"Finish {names} first."


async def check_prerequisites(db: AsyncSession, user: User | None, topic: Topic) -> GateResult:
    """Gating that explains itself.

    A locked door with no explanation is worse than no lock at all, so the
    result carries which topics are missing rather than a bare boolean.
    """
    rows = list(
        await db.execute(
            select(Prerequisite, Topic)
            .join(Topic, Topic.id == Prerequisite.requires_topic_id)
            .where(Prerequisite.topic_id == topic.id)
        )
    )
    required = [(link, required) for link, required in rows if link.hardness == "required"]
    if not required:
        return GateResult(unlocked=True, missing=[])

    if user is None:
        return GateResult(
            unlocked=False,
            missing=[{"slug": t.slug, "title": t.title} for _, t in required],
        )

    done = await db.scalars(
        select(UserProgress.entity_id).where(
            UserProgress.user_id == user.id,
            UserProgress.entity_type == "topic",
            UserProgress.status == "completed",
        )
    )
    completed = set(done)
    missing = [{"slug": t.slug, "title": t.title} for _, t in required if t.id not in completed]
    return GateResult(unlocked=not missing, missing=missing)


# -------------------------------------------------------------------- quizzes


async def start_attempt(db: AsyncSession, user: User, topic_slug: str) -> QuizAttempt:
    topic = await db.scalar(select(Topic).where(Topic.slug == topic_slug))
    if topic is None:
        raise NotFoundError(f"topic '{topic_slug}' not found")

    gate = await check_prerequisites(db, user, topic)
    if not gate.unlocked:
        raise LockedError(gate.reason or "Prerequisites not met")

    quiz = await db.scalar(select(Quiz).where(Quiz.topic_id == topic.id))
    if quiz is None:
        raise NotFoundError(f"topic '{topic_slug}' has no quiz")

    version = await db.scalar(select(ContentVersion).where(ContentVersion.is_current))
    attempt = QuizAttempt(
        user_id=user.id,
        quiz_id=quiz.id,
        content_version_id=version.id if version else None,
    )
    db.add(attempt)
    await db.commit()
    return attempt


@dataclass
class GradedQuestion:
    code: str
    stem: str
    level: str
    objectives: list[str]
    given: list[str]
    correct: list[str]
    is_correct: bool
    explanation: str
    options: list[dict]


@dataclass
class GradedAttempt:
    attempt_id: uuid.UUID
    score: float
    passed: bool
    pass_score: int
    total: int
    correct_count: int
    questions: list[GradedQuestion]
    weak_objectives: list[dict]


async def grade_attempt(
    db: AsyncSession, user: User, attempt_id: uuid.UUID, answers: dict[str, list[str]]
) -> GradedAttempt:
    """Grade server-side against the stored key.

    `answers` maps question code to the option codes the learner chose. Anything
    the browser sends beyond that is ignored: the score is computed here, from
    the database, and written here.
    """
    attempt = await db.get(QuizAttempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        # Same error for "not yours" as for "does not exist" — otherwise this is
        # an oracle for which attempt ids are real.
        raise NotFoundError("attempt not found")
    if attempt.submitted_at is not None:
        raise LearningError("this attempt has already been submitted")

    quiz = await db.scalar(
        select(Quiz)
        .where(Quiz.id == attempt.quiz_id)
        .options(selectinload(Quiz.questions).selectinload(QuizQuestion.options))
    )
    if quiz is None:
        raise NotFoundError("quiz not found")

    graded: list[GradedQuestion] = []
    correct_count = 0
    objective_hits: dict[str, list[bool]] = {}

    for question in quiz.questions:
        key = sorted(option.code for option in question.options if option.is_correct)
        given = sorted(set(answers.get(question.code, [])))

        # Ordering questions are scored on sequence, not on set membership.
        if question.type == "ordering":
            expected = [option.code for option in question.options if option.is_correct]
            is_correct = answers.get(question.code, []) == expected
        else:
            is_correct = given == key

        if is_correct:
            correct_count += 1

        for objective in question.objectives:
            objective_hits.setdefault(objective, []).append(is_correct)

        db.add(
            QuizAnswer(
                attempt_id=attempt.id,
                question_id=question.id,
                given=answers.get(question.code, []),
                is_correct=is_correct,
            )
        )

        graded.append(
            GradedQuestion(
                code=question.code,
                stem=question.stem,
                level=question.level,
                objectives=list(question.objectives),
                given=answers.get(question.code, []),
                correct=key,
                is_correct=is_correct,
                explanation=question.explanation,
                options=[
                    {
                        "id": option.code,
                        "text": option.text,
                        "correct": option.is_correct,
                        "note": option.note,
                    }
                    for option in question.options
                ],
            )
        )

    total = len(quiz.questions)
    score = round(100.0 * correct_count / total, 2) if total else 0.0
    passed = score >= quiz.pass_score

    attempt.submitted_at = datetime.now(UTC)
    attempt.score = score
    attempt.passed = passed

    progress = await db.scalar(
        select(UserProgress).where(
            UserProgress.user_id == user.id,
            UserProgress.entity_type == "quiz",
            UserProgress.entity_id == quiz.id,
        )
    )
    if progress is None:
        progress = UserProgress(
            user_id=user.id,
            entity_type="quiz",
            entity_id=quiz.id,
            status="in_progress",
            attempts=0,
            first_seen_at=datetime.now(UTC),
        )
        db.add(progress)
    progress.attempts += 1
    progress.score = max(score, progress.score or 0)
    progress.status = "completed" if passed else "failed"
    if passed and progress.completed_at is None:
        progress.completed_at = datetime.now(UTC)

    await db.commit()
    record_quiz_attempt(passed, str(quiz.topic_id))
    await evaluate_achievements_for(user.id)

    # Route the learner back to what they actually got wrong, rather than to the
    # top of the page.
    statements = {
        objective.code: objective.statement
        for objective in await db.scalars(
            select(Objective).where(Objective.topic_id == quiz.topic_id)
        )
    }
    weak = [
        {
            "code": code,
            "statement": statements.get(code, ""),
            "correct": sum(hits),
            "total": len(hits),
        }
        for code, hits in sorted(objective_hits.items())
        if not all(hits)
    ]

    log.info(
        "quiz_graded",
        user_id=str(user.id),
        quiz_id=str(quiz.id),
        score=score,
        passed=passed,
    )

    return GradedAttempt(
        attempt_id=attempt.id,
        score=score,
        passed=passed,
        pass_score=quiz.pass_score,
        total=total,
        correct_count=correct_count,
        questions=graded,
        weak_objectives=weak,
    )


# ------------------------------------------------------------ troubleshooting


async def submit_hypothesis(
    db: AsyncSession, user: User, topic_slug: str, scenario_code: str, body: str
) -> Hypothesis:
    item = await _troubleshooting_item(db, topic_slug, scenario_code)
    if len(body.strip()) < 30:
        raise LearningError(
            "Write a real diagnosis first — at least a sentence saying which "
            "resource is the bottleneck and which evidence points at it."
        )

    hypothesis = Hypothesis(user_id=user.id, item_id=item.id, body=body.strip())
    db.add(hypothesis)
    await db.commit()
    log.info("hypothesis_submitted", user_id=str(user.id), scenario=scenario_code)
    return hypothesis


async def reveal_solution(
    db: AsyncSession, user: User, topic_slug: str, scenario_code: str
) -> dict:
    """Serve the root cause — only once a hypothesis exists.

    This gate is the entire pedagogical value of a troubleshooting scenario. It
    is enforced here rather than in the UI, because a UI-only gate is a
    suggestion.
    """
    item = await _troubleshooting_item(db, topic_slug, scenario_code)

    if item.payload.get("reveal_policy") == "progressive":
        submitted = await db.scalar(
            select(func.count())
            .select_from(Hypothesis)
            .where(Hypothesis.user_id == user.id, Hypothesis.item_id == item.id)
        )
        if not submitted:
            raise LockedError(
                "Submit your diagnosis before the solution is revealed. "
                "Reading the answer first is how people learn to recognise "
                "problems they have seen and nothing else."
            )

    return dict(item.solution)


async def _troubleshooting_item(db: AsyncSession, topic_slug: str, code: str) -> TopicItem:
    topic_id = await db.scalar(select(Topic.id).where(Topic.slug == topic_slug))
    if topic_id is None:
        raise NotFoundError(f"topic '{topic_slug}' not found")
    item = await db.scalar(
        select(TopicItem).where(
            TopicItem.topic_id == topic_id,
            TopicItem.kind == "troubleshooting",
            TopicItem.content_id == code,
        )
    )
    if item is None:
        raise NotFoundError(f"scenario '{code}' not found")
    return item


# ------------------------------------------------------------------ dashboard


async def dashboard(db: AsyncSession, user: User) -> dict:
    done = await progress_map(db, user)

    topics = list(
        await db.scalars(
            select(Topic)
            .where(Topic.status == "published")
            .options(selectinload(Topic.module).selectinload(Module.course))
            .order_by(Topic.order)
        )
    )

    completed: list[dict] = []
    in_progress: list[dict] = []
    available: list[dict] = []

    for topic in topics:
        row = done.get(("topic", topic.id))
        entry = {
            "slug": topic.slug,
            "title": topic.title,
            "course": topic.module.course.title,
            "estimated_minutes": topic.estimated_minutes,
        }
        if row and row.status == "completed":
            completed.append(entry)
        elif row:
            in_progress.append(entry)
        else:
            available.append(entry)

    attempts = list(
        await db.scalars(
            select(QuizAttempt)
            .where(QuizAttempt.user_id == user.id, QuizAttempt.submitted_at.is_not(None))
            .order_by(QuizAttempt.submitted_at.desc())
            .limit(5)
        )
    )

    # Aggregate objective-level evidence across every kind of assessable, so
    # "proficient" means more than "passed the multiple choice".
    weak = await _weak_objectives(db, user)

    return {
        "display_name": user.display_name,
        "completed": completed,
        "in_progress": in_progress,
        "available": available[:5],
        "next_topic": (in_progress or available or [None])[0],
        "recent_attempts": [
            {
                "score": attempt.score,
                "passed": attempt.passed,
                "submitted_at": attempt.submitted_at,
            }
            for attempt in attempts
        ],
        "weak_objectives": weak,
        "totals": {
            "topics_completed": len(completed),
            "topics_total": len(topics),
            "quizzes_passed": sum(
                1 for key, row in done.items() if key[0] == "quiz" and row.status == "completed"
            ),
        },
    }


async def _weak_objectives(db: AsyncSession, user: User, limit: int = 5) -> list[dict]:
    """Objectives with failed evidence, worst first.

    Weighted by evidence type: getting a quiz question wrong is a nudge, failing
    a troubleshooting scenario is a real gap.
    """
    rows = list(
        await db.execute(
            select(QuizAnswer, QuizQuestion, Objective)
            .join(QuizAttempt, QuizAttempt.id == QuizAnswer.attempt_id)
            .join(QuizQuestion, QuizQuestion.id == QuizAnswer.question_id)
            .join(Quiz, Quiz.id == QuizQuestion.quiz_id)
            .join(Objective, Objective.topic_id == Quiz.topic_id)
            .where(QuizAttempt.user_id == user.id)
        )
    )

    scores: dict[str, dict] = {}
    for answer, question, objective in rows:
        if objective.code not in question.objectives:
            continue
        entry = scores.setdefault(
            objective.code,
            {"code": objective.code, "statement": objective.statement, "wrong": 0, "total": 0},
        )
        entry["total"] += EVIDENCE_WEIGHT["quiz"]
        if not answer.is_correct:
            entry["wrong"] += EVIDENCE_WEIGHT["quiz"]

    weak = [entry for entry in scores.values() if entry["wrong"] > 0]
    weak.sort(key=lambda entry: entry["wrong"] / entry["total"], reverse=True)
    return weak[:limit]


async def course_completion(db: AsyncSession, user: User | None) -> dict[str, dict]:
    """Per-course completion, for the roadmap."""
    if user is None:
        return {}

    done = await progress_map(db, user)
    completed_topics = {
        key[1] for key, row in done.items() if key[0] == "topic" and row.status == "completed"
    }

    result: dict[str, dict] = {}
    courses = list(
        await db.scalars(
            select(Course).options(selectinload(Course.modules).selectinload(Module.topics))
        )
    )
    for course in courses:
        topics = [t for module in course.modules for t in module.topics if t.status == "published"]
        done_count = sum(1 for t in topics if t.id in completed_topics)
        result[course.slug] = {"completed": done_count, "total": len(topics)}
    return result
