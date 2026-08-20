"""Achievements, competence and certificates.

Note what is missing from this router: there is no endpoint that grants an
achievement or issues a certificate from a request body. The two write paths
both mean "re-read the evidence you already have and tell me what it supports",
and the evidence comes from graded quiz answers and machine-verified lab checks
that a client cannot write either.

`GET /certificates/{code}` is the one deliberately public endpoint. A credential
nobody can check without an account is decoration, so this returns the holder,
the course and what it required — and nothing else about the person.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import current_user
from app.db.session import get_session
from app.models.attainment import Certificate, UserAchievement
from app.models.curriculum import Course, Module, Topic
from app.models.identity import User
from app.schemas.attainment import (
    AchievementOut,
    CertificateOut,
    CertificateVerificationOut,
    CourseCompetenceOut,
    ObjectiveScoreOut,
    TopicCompetenceOut,
)
from app.services.achievements import evaluate, issue_certificate
from app.services.competence import PROFICIENT, course_competence, topic_competence

router = APIRouter(tags=["attainment"])


@router.get("/achievements", response_model=list[AchievementOut])
async def my_achievements(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> list[AchievementOut]:
    rows = await session.scalars(
        select(UserAchievement)
        .where(UserAchievement.user_id == user.id)
        .order_by(UserAchievement.earned_at.desc())
    )
    return [
        AchievementOut(
            code=row.code,
            scope=row.scope,
            title=row.title,
            detail=row.detail,
            earned_at=row.earned_at,
        )
        for row in rows
    ]


@router.post("/achievements/evaluate", response_model=list[AchievementOut])
async def evaluate_achievements(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> list[AchievementOut]:
    """Re-read the evidence and grant anything newly earned. Returns only what is new."""
    granted = await evaluate(session, user)
    return [
        AchievementOut(code=g.code, scope=g.scope, title=g.title, detail=g.detail) for g in granted
    ]


@router.get("/topics/{slug}/competence", response_model=TopicCompetenceOut)
async def my_topic_competence(
    slug: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> TopicCompetenceOut:
    topic = await session.scalar(select(Topic).where(Topic.slug == slug))
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="topic not found")

    competence = await topic_competence(session, user, topic)
    return TopicCompetenceOut(
        topic_slug=competence.topic_slug,
        topic_title=competence.topic_title,
        score=competence.score,
        mastered=competence.mastered,
        proficient_at=PROFICIENT,
        objectives=[
            ObjectiveScoreOut(
                code=o.code,
                statement=o.statement,
                score=o.score,
                proficient=o.proficient,
                sources=o.sources,
            )
            for o in competence.objectives
        ],
    )


@router.get("/courses/{slug}/competence", response_model=CourseCompetenceOut)
async def my_course_competence(
    slug: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> CourseCompetenceOut:
    course = await session.scalar(
        select(Course)
        .where(Course.slug == slug)
        .options(selectinload(Course.modules).selectinload(Module.topics))
    )
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="course not found")

    summary = await course_competence(session, user, course)
    return CourseCompetenceOut(
        course_slug=summary["course_slug"],
        course_code=summary["course_code"],
        course_title=summary["course_title"],
        score=summary["score"],
        mastered=summary["mastered"],
        topics_total=summary["topics_total"],
        topics_mastered=summary["topics_mastered"],
        topics=[
            TopicCompetenceOut(
                topic_slug=t.topic_slug,
                topic_title=t.topic_title,
                score=t.score,
                mastered=t.mastered,
                proficient_at=PROFICIENT,
                objectives=[
                    ObjectiveScoreOut(
                        code=o.code,
                        statement=o.statement,
                        score=o.score,
                        proficient=o.proficient,
                        sources=o.sources,
                    )
                    for o in t.objectives
                ],
            )
            for t in summary["topics"]
        ],
    )


@router.get("/certificates", response_model=list[CertificateOut])
async def my_certificates(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> list[CertificateOut]:
    rows = await session.scalars(
        select(Certificate)
        .where(Certificate.user_id == user.id)
        .order_by(Certificate.issued_at.desc())
    )
    return [_certificate_out(row) for row in rows]


@router.post("/courses/{slug}/certificate", response_model=CertificateOut)
async def claim_certificate(
    slug: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> CertificateOut:
    """Ask for a certificate. The evidence decides, not the request.

    409 rather than 403 when the bar is not met: nothing is forbidden, the state
    simply does not support it yet, and the response says which topics are short.
    """
    certificate = await issue_certificate(session, user, slug)
    if certificate is None:
        course = await session.scalar(
            select(Course)
            .where(Course.slug == slug)
            .options(selectinload(Course.modules).selectinload(Module.topics))
        )
        if course is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="course not found")
        summary = await course_competence(session, user, course)
        short = [t.topic_slug for t in summary["topics"] if not t.mastered]
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                "Not yet: every objective in every topic has to be demonstrated. "
                f"Still short on: {', '.join(short) or 'nothing — try again'}."
            ),
        )
    return _certificate_out(certificate)


@router.get("/certificates/{code}", response_model=CertificateVerificationOut)
async def verify_certificate(
    code: str, session: AsyncSession = Depends(get_session)
) -> CertificateVerificationOut:
    """Public. Anyone holding the code can check what it attests to.

    Returns the holder's display name and the course — never their email, their
    id, or anything else about them. The code is the credential; it should not
    also be a lookup key into a person.
    """
    certificate = await session.scalar(select(Certificate).where(Certificate.code == code))
    if certificate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no certificate with that code")

    return CertificateVerificationOut(
        code=certificate.code,
        valid=True,
        holder_name=certificate.holder_name,
        course_code=certificate.course_code,
        course_title=certificate.course_title,
        topics_completed=certificate.topics_completed,
        weakest_objective_score=certificate.weakest_objective_score,
        issued_at=certificate.issued_at,
    )


def _certificate_out(certificate: Certificate) -> CertificateOut:
    return CertificateOut(
        code=certificate.code,
        course_code=certificate.course_code,
        course_title=certificate.course_title,
        holder_name=certificate.holder_name,
        topics_completed=certificate.topics_completed,
        weakest_objective_score=certificate.weakest_objective_score,
        issued_at=certificate.issued_at,
    )
