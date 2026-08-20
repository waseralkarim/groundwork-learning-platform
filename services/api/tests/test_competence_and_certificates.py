"""The competence model, achievements and certificates.

The requirement under test is the one that is easiest to agree with and easiest
to quietly break: **a passed multiple-choice quiz must not mark a learner
proficient.** Every shortcut implementation of "is this done" violates it, so it
is asserted directly here rather than left to a design document.

These run against real PostgreSQL and the real curriculum, so the objective
mappings being exercised are the ones learners actually meet.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.content.ingest import ingest
from app.content.loader import load_content
from app.models.attainment import Certificate, UserAchievement
from app.models.curriculum import (
    Course,
    Lab,
    Module,
    Quiz,
    QuizQuestion,
    Topic,
    TopicItem,
)
from app.models.identity import Hypothesis, QuizAnswer, QuizAttempt, User, UserProgress
from app.services import achievements, auth, competence

pytestmark = pytest.mark.skipif(
    os.environ.get("POSTGRES_HOST") in (None, "localhost"),
    reason="no database available",
)

TEST_DATABASE = "groundwork_attainment_test"
REPO_CONTENT = Path("/content")


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    from sqlalchemy import text

    from app.core.config import get_settings
    from app.db.base import Base

    settings = get_settings()
    admin_url = settings.database_url
    test_url = admin_url.rsplit("/", 1)[0] + f"/{TEST_DATABASE}"

    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as connection:
        exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DATABASE}
        )
        if not exists:
            await connection.execute(text(f'CREATE DATABASE "{TEST_DATABASE}"'))
    await admin_engine.dispose()

    # Committed separately: inside the create_all transaction, a failure rolls
    # the extension back and every later run fails identically.
    prep = create_async_engine(test_url, isolation_level="AUTOCOMMIT")
    async with prep.connect() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    await prep.dispose()

    engine = create_async_engine(test_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with maker() as session:
        await session.execute(
            text("TRUNCATE learning_paths, courses, content_versions, users CASCADE")
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(db: AsyncSession) -> AsyncSession:
    if not REPO_CONTENT.is_dir():
        pytest.skip("content not mounted")
    tree = load_content(REPO_CONTENT)
    assert tree.ok, "\n".join(str(e) for e in tree.errors)
    await ingest(db, tree, "test")
    return db


async def make_user(db: AsyncSession, email: str = "learner@example.com") -> User:
    user, _ = await auth.register(
        db, email=email, password="a-perfectly-fine-passphrase", display_name="Ada Lovelace"
    )
    return user


async def a_topic(db: AsyncSession, slug: str = "processes") -> Topic:
    topic = await db.scalar(select(Topic).where(Topic.slug == slug))
    assert topic is not None
    return topic


async def answer_every_question_correctly(db: AsyncSession, user: User, topic: Topic) -> None:
    """Perfect quiz evidence, and nothing else."""
    quiz = await db.scalar(
        select(Quiz)
        .where(Quiz.topic_id == topic.id)
        .options(selectinload(Quiz.questions).selectinload(QuizQuestion.options))
    )
    assert quiz is not None
    attempt = QuizAttempt(user_id=user.id, quiz_id=quiz.id, score=100, passed=True)
    db.add(attempt)
    await db.flush()
    for question in quiz.questions:
        db.add(
            QuizAnswer(
                attempt_id=attempt.id,
                question_id=question.id,
                given=[o.code for o in question.options if o.is_correct],
                is_correct=True,
            )
        )
    await db.commit()


async def complete(db: AsyncSession, user: User, entity_type: str, entity_id, score=None) -> None:
    db.add(
        UserProgress(
            user_id=user.id,
            entity_type=entity_type,
            entity_id=entity_id,
            status="completed",
            score=score,
        )
    )
    await db.commit()


async def do_the_actual_work(db: AsyncSession, user: User, topic: Topic) -> None:
    """Everything the topic asks for: quiz, labs, exercises, scenarios, assessment."""
    await answer_every_question_correctly(db, user, topic)

    for lab in await db.scalars(select(Lab).where(Lab.topic_id == topic.id)):
        await complete(db, user, "lab", lab.id)

    for item in await db.scalars(select(TopicItem).where(TopicItem.topic_id == topic.id)):
        await complete(db, user, item.kind, item.id, score=90)


# ------------------------------------------------------- the central guarantee


async def test_quiz_alone_never_reaches_proficiency(seeded: AsyncSession) -> None:
    """The requirement: passing the multiple-choice quiz is not competence.

    A learner who answers every question in the topic correctly — a perfect
    score, nothing wrong — must still not be marked proficient, because the
    evidence types that are hard to fake contributed nothing.
    """
    user = await make_user(seeded)
    topic = await a_topic(seeded)

    await answer_every_question_correctly(seeded, user, topic)
    result = await competence.topic_competence(seeded, user, topic)

    assert result.score > 0, "a perfect quiz should count for something"
    assert result.score < competence.PROFICIENT, (
        f"a perfect quiz scored {result.score}, which clears the proficiency bar — "
        "the whole model is defeated"
    )
    assert not result.mastered
    assert all(not o.proficient for o in result.objectives)


async def test_doing_the_work_reaches_proficiency(seeded: AsyncSession) -> None:
    user = await make_user(seeded)
    topic = await a_topic(seeded)

    await do_the_actual_work(seeded, user, topic)
    result = await competence.topic_competence(seeded, user, topic)

    assert result.mastered, f"objectives: {[(o.code, o.score) for o in result.objectives]}"
    assert result.score >= competence.PROFICIENT


async def test_the_score_is_the_weakest_objective_not_the_average(seeded: AsyncSession) -> None:
    """Strength in seven objectives must not cover for weakness in the eighth."""
    user = await make_user(seeded)
    topic = await a_topic(seeded)

    await do_the_actual_work(seeded, user, topic)
    result = await competence.topic_competence(seeded, user, topic)

    scores = [o.score for o in result.objectives]
    assert result.score == min(scores)
    if len(set(scores)) > 1:
        average = sum(scores) / len(scores)
        assert result.score < average, "taking the minimum must be observable"


async def test_repeating_a_quiz_adds_nothing(seeded: AsyncSession) -> None:
    """Volume must not substitute for depth: twenty attempts is not twenty times.

    Evidence is counted per question, not per answer row, so retaking a quiz
    cannot inflate a score.
    """
    user = await make_user(seeded)
    topic = await a_topic(seeded)

    await answer_every_question_correctly(seeded, user, topic)
    once = await competence.topic_competence(seeded, user, topic)

    for _ in range(19):
        await answer_every_question_correctly(seeded, user, topic)
    twenty = await competence.topic_competence(seeded, user, topic)

    assert [o.score for o in once.objectives] == [o.score for o in twenty.objectives]
    assert not twenty.mastered


# ------------------------------------------------------------------ certificates


async def test_a_certificate_is_refused_without_the_evidence(seeded: AsyncSession) -> None:
    """Marking every topic complete is not the same as demonstrating anything."""
    user = await make_user(seeded)
    for topic in await seeded.scalars(select(Topic)):
        await complete(seeded, user, "topic", topic.id)

    certificate = await achievements.issue_certificate(seeded, user, "computing-foundations")
    assert certificate is None


async def test_a_certificate_is_issued_when_every_objective_is_demonstrated(
    seeded: AsyncSession,
) -> None:
    user = await make_user(seeded)
    course = await seeded.scalar(
        select(Course)
        .where(Course.slug == "computing-foundations")
        .options(selectinload(Course.modules).selectinload(Module.topics))
    )
    assert course is not None
    for module in course.modules:
        for topic in module.topics:
            await do_the_actual_work(seeded, user, topic)

    certificate = await achievements.issue_certificate(seeded, user, "computing-foundations")
    assert certificate is not None
    assert certificate.code.startswith("GW-A01-")
    assert certificate.holder_name == "Ada Lovelace"
    assert certificate.weakest_objective_score >= competence.PROFICIENT


async def test_claiming_twice_returns_the_same_certificate(seeded: AsyncSession) -> None:
    """A second claim must not mint a second credential for the same course."""
    user = await make_user(seeded)
    course = await seeded.scalar(
        select(Course)
        .where(Course.slug == "computing-foundations")
        .options(selectinload(Course.modules).selectinload(Module.topics))
    )
    for module in course.modules:
        for topic in module.topics:
            await do_the_actual_work(seeded, user, topic)

    first = await achievements.issue_certificate(seeded, user, "computing-foundations")
    second = await achievements.issue_certificate(seeded, user, "computing-foundations")

    assert first is not None and second is not None
    assert first.code == second.code
    count = len(
        list(await seeded.scalars(select(Certificate).where(Certificate.user_id == user.id)))
    )
    assert count == 1


async def test_certificate_codes_are_not_derived_from_the_user(seeded: AsyncSession) -> None:
    """Two learners must not produce guessable, related codes."""
    codes = set()
    course = await seeded.scalar(
        select(Course)
        .where(Course.slug == "computing-foundations")
        .options(selectinload(Course.modules).selectinload(Module.topics))
    )
    for index in range(2):
        user = await make_user(seeded, email=f"holder{index}@example.com")
        for module in course.modules:
            for topic in module.topics:
                await do_the_actual_work(seeded, user, topic)
        certificate = await achievements.issue_certificate(seeded, user, "computing-foundations")
        assert certificate is not None
        codes.add(certificate.code)

    assert len(codes) == 2
    first, second = sorted(codes)
    assert first.split("-")[-1] != second.split("-")[-1]


# ----------------------------------------------------------------- achievements


async def test_achievements_are_idempotent(seeded: AsyncSession) -> None:
    user = await make_user(seeded)
    topic = await a_topic(seeded)
    await complete(seeded, user, "topic", topic.id)

    first = await achievements.evaluate(seeded, user)
    second = await achievements.evaluate(seeded, user)

    assert [g.code for g in first] == ["first-topic"]
    assert second == [], "re-evaluating must not grant the same achievement again"

    rows = list(
        await seeded.scalars(select(UserAchievement).where(UserAchievement.user_id == user.id))
    )
    assert len(rows) == 1


async def test_mastery_achievement_needs_real_evidence(seeded: AsyncSession) -> None:
    """topic-mastered is the achievement that cannot be clicked into existence."""
    user = await make_user(seeded)
    topic = await a_topic(seeded)

    await answer_every_question_correctly(seeded, user, topic)
    await complete(seeded, user, "topic", topic.id)
    granted = await achievements.evaluate(seeded, user)
    assert "topic-mastered" not in [g.code for g in granted]

    await do_the_actual_work(seeded, user, topic)
    granted = await achievements.evaluate(seeded, user)
    assert ("topic-mastered", topic.slug) in [(g.code, g.scope) for g in granted]


async def test_diagnostician_counts_hypotheses_not_reveals(seeded: AsyncSession) -> None:
    user = await make_user(seeded)
    scenarios = list(
        await seeded.scalars(select(TopicItem).where(TopicItem.kind == "troubleshooting"))
    )
    assert len(scenarios) >= 3

    for scenario in scenarios[:2]:
        seeded.add(Hypothesis(user_id=user.id, item_id=scenario.id, body="a guess worth making"))
    await seeded.commit()
    assert "diagnostician" not in [g.code for g in await achievements.evaluate(seeded, user)]

    seeded.add(Hypothesis(user_id=user.id, item_id=scenarios[2].id, body="a third guess"))
    await seeded.commit()
    assert "diagnostician" in [g.code for g in await achievements.evaluate(seeded, user)]
