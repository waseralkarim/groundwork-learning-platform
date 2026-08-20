"""The competence model: what a learner has actually demonstrated.

The requirement this exists to satisfy: **a passed multiple-choice quiz must not
mark someone proficient.** That is easy to agree with and easy to quietly
violate, because the simplest implementation of "is this topic done" counts
completions, and a quiz completion counts the same as diagnosing a broken system.

Three rules, in order of importance.

**1. An objective is scored against the evidence it actually offers.**
Every objective declares what assesses it (`assessed_by`), and the linter refuses
content where that list is empty. So the denominator is not an invented
hundred-point scale — it is the weighted evidence this particular objective can
produce. An objective backed by two quiz questions and one lab is scored out of
those three things, which means a learner who does everything the topic asks
reaches full marks. A fixed scale cannot promise that: it makes mastery depend on
how many assessables an author happened to write.

**2. Evidence is weighted by how hard it is to fake.**

    quiz answer          1    you can guess a four-option question
    exercise             2    written, but self-marked
    lab step             3    a machine checked the state you produced
    troubleshooting      4    you committed to a hypothesis before the reveal
    assessment part      4    applied reasoning against a rubric

**3. Proficiency requires evidence that is not just quizzes.** Rule 1 alone would
let an objective with eight quiz questions and one lab clear the bar on quizzes
only, at 8/11. So where strong evidence is available for an objective, some of it
must actually be present. This is the §35 guarantee, stated as a condition rather
than left to emerge from the arithmetic — and it is what
`test_quiz_alone_never_reaches_proficiency` pins down.

A topic's proficiency is then the **minimum** across its objectives, never the
average. You are as strong as your weakest objective. Averaging is what lets
someone ace the quiz, skip the labs, and be called proficient.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.curriculum import (
    Course,
    Lab,
    Module,
    Objective,
    Quiz,
    Topic,
    TopicItem,
)
from app.models.identity import QuizAnswer, QuizAttempt, User, UserProgress

WEIGHT = {
    "quiz": 1,
    "exercise": 2,
    "lab": 3,
    "troubleshooting": 4,
    "assessment": 4,
    "interview": 1,
}

# Evidence that a learner cannot produce by recognising an answer.
STRONG = frozenset({"lab", "troubleshooting", "assessment"})

# Out of 100, as a proportion of the evidence the objective offers.
PROFICIENT = 60


@dataclass
class ObjectiveScore:
    code: str
    statement: str
    score: int = 0
    # What was demonstrated, by kind — shown to the learner, because "why am I
    # not proficient" deserves a concrete answer rather than a number.
    sources: dict[str, int] = field(default_factory=dict)
    available: dict[str, int] = field(default_factory=dict)
    proficient: bool = False

    @property
    def strong_available(self) -> bool:
        return any(kind in STRONG for kind in self.available)

    @property
    def strong_demonstrated(self) -> bool:
        return any(kind in STRONG for kind in self.sources)


@dataclass
class TopicCompetence:
    topic_slug: str
    topic_title: str
    objectives: list[ObjectiveScore]

    @property
    def score(self) -> int:
        """The weakest objective. Not the average — see the module docstring."""
        return min((o.score for o in self.objectives), default=0)

    @property
    def mastered(self) -> bool:
        return bool(self.objectives) and all(o.proficient for o in self.objectives)

    @property
    def weakest(self) -> ObjectiveScore | None:
        return min(self.objectives, key=lambda o: o.score, default=None)


async def topic_competence(db: AsyncSession, user: User, topic: Topic) -> TopicCompetence:
    """Score every objective in one topic against the evidence on record."""
    objectives = list(await db.scalars(select(Objective).where(Objective.topic_id == topic.id)))
    if not objectives:
        return TopicCompetence(topic.slug, topic.title, [])

    scores = {
        objective.code: ObjectiveScore(code=objective.code, statement=objective.statement)
        for objective in objectives
    }

    await _collect_quiz(db, user, topic, scores)
    await _collect_completables(db, user, topic, scores)

    for entry in scores.values():
        available = sum(entry.available.values())
        achieved = sum(entry.sources.values())
        entry.score = round(100 * achieved / available) if available else 0
        entry.proficient = entry.score >= PROFICIENT and (
            entry.strong_demonstrated or not entry.strong_available
        )

    return TopicCompetence(
        topic_slug=topic.slug,
        topic_title=topic.title,
        objectives=[scores[o.code] for o in objectives],
    )


def _offer(entry: ObjectiveScore, kind: str, weight: int) -> None:
    entry.available[kind] = entry.available.get(kind, 0) + weight


def _credit(entry: ObjectiveScore, kind: str, weight: int) -> None:
    entry.sources[kind] = entry.sources.get(kind, 0) + weight


async def _collect_quiz(
    db: AsyncSession, user: User, topic: Topic, scores: dict[str, ObjectiveScore]
) -> None:
    """One credit per question, not per answer.

    Counting answers would mean a learner who retakes the same quiz twenty times
    accumulates twenty times the evidence, which is volume standing in for
    understanding. A question answered correctly at any point counts once.
    """
    quiz = await db.scalar(
        select(Quiz).where(Quiz.topic_id == topic.id).options(selectinload(Quiz.questions))
    )
    if quiz is None:
        return

    questions = {question.id: question for question in quiz.questions}
    for question in quiz.questions:
        for code in question.objectives:
            if code in scores:
                _offer(scores[code], "quiz", WEIGHT["quiz"])

    correct_ids = set(
        await db.scalars(
            select(QuizAnswer.question_id)
            .join(QuizAttempt, QuizAttempt.id == QuizAnswer.attempt_id)
            .where(QuizAttempt.user_id == user.id, QuizAnswer.is_correct.is_(True))
        )
    )
    for question_id in correct_ids:
        question = questions.get(question_id)
        if question is None:
            continue
        for code in question.objectives:
            if code in scores:
                _credit(scores[code], "quiz", WEIGHT["quiz"])


async def _collect_completables(
    db: AsyncSession, user: User, topic: Topic, scores: dict[str, ObjectiveScore]
) -> None:
    """Labs, exercises, troubleshooting scenarios, assessments.

    Each declares the objectives it assesses, which is what makes any of this
    possible — the content model requires that mapping and the linter enforces
    it, so the denominator here is derived from the curriculum rather than
    guessed at.
    """
    progress = {
        (row.entity_type, row.entity_id): row
        for row in await db.scalars(select(UserProgress).where(UserProgress.user_id == user.id))
    }

    labs = list(await db.scalars(select(Lab).where(Lab.topic_id == topic.id)))
    items = list(await db.scalars(select(TopicItem).where(TopicItem.topic_id == topic.id)))

    for lab in labs:
        row = progress.get(("lab", lab.id))
        done = row is not None and row.status == "completed"
        for code in lab.objectives:
            if code not in scores:
                continue
            _offer(scores[code], "lab", WEIGHT["lab"])
            if done:
                _credit(scores[code], "lab", WEIGHT["lab"])

    for item in items:
        weight = WEIGHT.get(item.kind)
        if weight is None:
            continue
        row = progress.get((item.kind, item.id))
        done = row is not None and row.status == "completed"
        for code in item.objectives:
            if code not in scores:
                continue
            _offer(scores[code], item.kind, weight)
            if done:
                # A scored item counts in proportion to the score, so scraping a
                # pass on an assessment is not the same as doing it well.
                share = (row.score / 100) if row.score is not None else 1.0
                _credit(scores[code], item.kind, round(weight * max(0.0, min(1.0, share))))


async def course_competence(db: AsyncSession, user: User, course: Course) -> dict:
    """Roll a course up from its topics, again by the weakest link."""
    topics = [
        topic for module in course.modules for topic in module.topics if topic.status == "published"
    ]
    per_topic = [await topic_competence(db, user, topic) for topic in topics]

    return {
        "course_slug": course.slug,
        "course_code": course.code,
        "course_title": course.title,
        "topics": per_topic,
        "topics_total": len(per_topic),
        "topics_mastered": sum(1 for t in per_topic if t.mastered),
        "score": min((t.score for t in per_topic), default=0),
        "mastered": bool(per_topic) and all(t.mastered for t in per_topic),
    }


async def load_course(db: AsyncSession, slug: str) -> Course | None:
    return await db.scalar(
        select(Course)
        .where(Course.slug == slug)
        .options(selectinload(Course.modules).selectinload(Module.topics))
    )


__all__ = [
    "PROFICIENT",
    "STRONG",
    "WEIGHT",
    "ObjectiveScore",
    "TopicCompetence",
    "course_competence",
    "load_course",
    "topic_competence",
]
