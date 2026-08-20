"""Achievement rules and certificate issuance.

Rules live here as code rather than as rows, because they are logic. A rule
engine driven by a table would be a worse, unreadable version of the functions
below, and nobody would be able to answer "why did I get this?" without running
a query.

Two properties hold for everything in this module:

**Nothing is granted from a request body.** A client can only ask the server to
re-evaluate; the evidence is read from the database each time. There is no
endpoint that accepts an achievement code, and there is no path that mints a
certificate for a course the evidence does not support.

**Everything is idempotent.** Re-evaluation is safe to run on every quiz
submission and every progress write, which it is, because a unique constraint —
not careful code — is what prevents duplicates.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.attainment import Certificate, UserAchievement
from app.models.curriculum import Course, Module, Topic
from app.models.identity import Hypothesis, User, UserProgress
from app.services.competence import course_competence, topic_competence

log = get_logger(__name__)


@dataclass
class Granted:
    code: str
    scope: str
    title: str
    detail: str
    evidence: dict


async def evaluate(db: AsyncSession, user: User) -> list[Granted]:
    """Re-evaluate every rule for one learner. Returns only what is new."""
    granted: list[Granted] = []

    for rule in (_topics_mastered, _diagnostician, _lab_complete, _first_topic):
        granted.extend(await rule(db, user))

    fresh: list[Granted] = []
    for item in granted:
        if await _record(db, user, item):
            fresh.append(item)

    if fresh:
        await db.commit()
        log.info(
            "achievements_granted",
            user_id=str(user.id),
            codes=[item.code for item in fresh],
        )
    return fresh


async def _record(db: AsyncSession, user: User, item: Granted) -> bool:
    """Insert one achievement. False if it was already held.

    Relies on the unique constraint rather than a pre-check, because two
    concurrent evaluations — a quiz submission and a progress write in the same
    second — would both pass a pre-check and one would fail on insert anyway.
    """
    existing = await db.scalar(
        select(UserAchievement.id).where(
            UserAchievement.user_id == user.id,
            UserAchievement.code == item.code,
            UserAchievement.scope == item.scope,
        )
    )
    if existing:
        return False

    db.add(
        UserAchievement(
            user_id=user.id,
            code=item.code,
            scope=item.scope,
            title=item.title,
            detail=item.detail,
            evidence=item.evidence,
        )
    )
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return False
    return True


# ----------------------------------------------------------------------- rules


async def _published_topics(db: AsyncSession) -> list[Topic]:
    return list(await db.scalars(select(Topic).where(Topic.status == "published")))


async def _first_topic(db: AsyncSession, user: User) -> list[Granted]:
    """The first topic finished properly. Everything after this is easier."""
    rows = await db.scalars(
        select(UserProgress).where(
            UserProgress.user_id == user.id,
            UserProgress.entity_type == "topic",
            UserProgress.status == "completed",
        )
    )
    completed = list(rows)
    if not completed:
        return []
    return [
        Granted(
            code="first-topic",
            scope="",
            title="Off the ground",
            detail="Finished your first topic end to end.",
            evidence={"topics_completed": len(completed)},
        )
    ]


async def _topics_mastered(db: AsyncSession, user: User) -> list[Granted]:
    """Mastery of a topic — every objective demonstrated, not merely visited.

    This is the achievement that means something, because it is the only one a
    learner cannot get by clicking through. The weakest objective has to clear
    the bar, so skipping the labs leaves it unearned no matter how many quizzes
    are passed.
    """
    granted: list[Granted] = []
    for topic in await _published_topics(db):
        competence = await topic_competence(db, user, topic)
        if not competence.mastered:
            continue
        granted.append(
            Granted(
                code="topic-mastered",
                scope=topic.slug,
                title=f"Mastered: {topic.title}",
                detail=(
                    f"Every objective demonstrated. Weakest was "
                    f"{competence.weakest.code if competence.weakest else '?'} "
                    f"at {competence.score}/100."
                ),
                evidence={
                    "score": competence.score,
                    "objectives": {o.code: o.score for o in competence.objectives},
                },
            )
        )
    return granted


async def _diagnostician(db: AsyncSession, user: User) -> list[Granted]:
    """Committed to a hypothesis before seeing the answer, three times.

    Deliberately counts hypotheses rather than scenarios completed: the value of
    a troubleshooting scenario is entirely in guessing first, and the gate that
    enforces it is the same one this counts.
    """
    count = len(list(await db.scalars(select(Hypothesis).where(Hypothesis.user_id == user.id))))
    if count < 3:
        return []
    return [
        Granted(
            code="diagnostician",
            scope="",
            title="Diagnostician",
            detail="Committed to a hypothesis before the reveal, three times over.",
            evidence={"hypotheses": count},
        )
    ]


async def _lab_complete(db: AsyncSession, user: User) -> list[Granted]:
    """Every lab in a topic verified. Labs are where the learning is."""
    granted: list[Granted] = []
    topics = await _published_topics(db)
    progress = {
        (row.entity_type, row.entity_id): row
        for row in await db.scalars(select(UserProgress).where(UserProgress.user_id == user.id))
    }

    for topic in topics:
        labs = list(
            await db.scalars(
                select(Topic).where(Topic.id == topic.id).options(selectinload(Topic.labs))
            )
        )
        lab_list = labs[0].labs if labs else []
        if not lab_list:
            continue
        done = [
            lab
            for lab in lab_list
            if (row := progress.get(("lab", lab.id))) is not None and row.status == "completed"
        ]
        if len(done) != len(lab_list):
            continue
        granted.append(
            Granted(
                code="labs-cleared",
                scope=topic.slug,
                title=f"Hands on: {topic.title}",
                detail=f"Verified every one of the {len(lab_list)} labs in this topic.",
                evidence={"labs": len(lab_list)},
            )
        )
    return granted


# ---------------------------------------------------------------- certificates


async def issue_certificate(db: AsyncSession, user: User, course_slug: str) -> Certificate | None:
    """Issue a certificate if — and only if — the evidence supports it.

    Gated on the competence model rather than on completion: every objective in
    every topic of the course has to clear the proficiency bar. Returning None
    is the normal outcome for someone who has finished the reading and not the
    work, and that is the entire point of having a certificate at all.
    """
    course = await db.scalar(
        select(Course)
        .where(Course.slug == course_slug)
        .options(selectinload(Course.modules).selectinload(Module.topics))
    )
    if course is None:
        return None

    existing = await db.scalar(
        select(Certificate).where(
            Certificate.user_id == user.id, Certificate.course_id == course.id
        )
    )
    if existing is not None:
        return existing

    summary = await course_competence(db, user, course)
    if not summary["mastered"]:
        return None

    certificate = Certificate(
        user_id=user.id,
        course_id=course.id,
        # Unguessable and unrelated to any user or course id — a code derived
        # from those would let a leaked id enumerate certificates.
        code=f"GW-{course.code}-{secrets.token_urlsafe(9).upper().replace('_', '-')}",
        holder_name=user.display_name,
        course_title=course.title,
        course_code=course.code,
        topics_completed=summary["topics_total"],
        weakest_objective_score=summary["score"],
        evidence={
            "topics": {
                topic.topic_slug: {
                    "score": topic.score,
                    "objectives": {o.code: o.score for o in topic.objectives},
                }
                for topic in summary["topics"]
            }
        },
    )
    db.add(certificate)
    await db.commit()
    await db.refresh(certificate)
    log.info(
        "certificate_issued",
        user_id=str(user.id),
        course=course.code,
        weakest=summary["score"],
    )
    return certificate


__all__ = ["Granted", "evaluate", "issue_certificate"]
