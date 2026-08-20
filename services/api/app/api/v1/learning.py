"""Progress, quiz attempts, troubleshooting reveal, dashboard."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, Db, OptionalUser, verify_origin
from app.models.curriculum import Quiz, Topic
from app.services import learning

router = APIRouter(tags=["learning"])
protected = APIRouter(dependencies=[Depends(verify_origin)], tags=["learning"])


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, learning.NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, learning.LockedError):
        return HTTPException(status.HTTP_423_LOCKED, detail=str(exc))
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ------------------------------------------------------------------- progress


class ProgressIn(BaseModel):
    status: str = Field(pattern="^(in_progress|completed)$")


class ProgressOut(BaseModel):
    entity_type: str
    entity_id: str
    status: str
    score: float | None
    attempts: int
    completed_at: datetime | None


@protected.put("/topics/{slug}/progress", response_model=ProgressOut)
async def set_topic_progress(slug: str, body: ProgressIn, user: CurrentUser, db: Db) -> ProgressOut:
    topic = await db.scalar(select(Topic).where(Topic.slug == slug))
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"topic '{slug}' not found")

    row = await learning.set_progress(
        db, user, entity_type="topic", entity_id=topic.id, status=body.status
    )
    return ProgressOut(
        entity_type=row.entity_type,
        entity_id=str(row.entity_id),
        status=row.status,
        score=row.score,
        attempts=row.attempts,
        completed_at=row.completed_at,
    )


@router.get("/progress/me", response_model=list[ProgressOut])
async def my_progress(user: CurrentUser, db: Db) -> list[ProgressOut]:
    rows = await learning.progress_map(db, user)
    return [
        ProgressOut(
            entity_type=row.entity_type,
            entity_id=str(row.entity_id),
            status=row.status,
            score=row.score,
            attempts=row.attempts,
            completed_at=row.completed_at,
        )
        for row in rows.values()
    ]


class GateOut(BaseModel):
    unlocked: bool
    reason: str | None
    missing: list[dict]


@router.get("/topics/{slug}/gate", response_model=GateOut)
async def topic_gate(slug: str, user: OptionalUser, db: Db) -> GateOut:
    topic = await db.scalar(select(Topic).where(Topic.slug == slug))
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"topic '{slug}' not found")
    gate = await learning.check_prerequisites(db, user, topic)
    return GateOut(unlocked=gate.unlocked, reason=gate.reason, missing=gate.missing)


# -------------------------------------------------------------------- quizzes


class AttemptStarted(BaseModel):
    attempt_id: str
    question_count: int
    pass_score: int


@protected.post(
    "/topics/{slug}/quiz/attempts",
    response_model=AttemptStarted,
    status_code=status.HTTP_201_CREATED,
)
async def start_quiz_attempt(slug: str, user: CurrentUser, db: Db) -> AttemptStarted:
    try:
        attempt = await learning.start_attempt(db, user, slug)
    except learning.LearningError as exc:
        raise _http(exc) from exc

    # Counted with a query rather than len(quiz.questions): touching a lazy
    # relationship here would attempt IO outside the async context and raise
    # MissingGreenlet. Async SQLAlchemy has no implicit lazy loading.
    quiz = await db.scalar(
        select(Quiz).where(Quiz.id == attempt.quiz_id).options(selectinload(Quiz.questions))
    )
    if quiz is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="quiz not found")

    return AttemptStarted(
        attempt_id=str(attempt.id),
        question_count=len(quiz.questions),
        pass_score=quiz.pass_score,
    )


class SubmitIn(BaseModel):
    # question code -> chosen option codes
    answers: dict[str, list[str]] = Field(default_factory=dict)


class GradedQuestionOut(BaseModel):
    id: str
    stem: str
    level: str
    objectives: list[str]
    given: list[str]
    correct: list[str]
    is_correct: bool
    explanation: str
    options: list[dict]


class GradedOut(BaseModel):
    """Answer keys appear here and only here — after grading, for this attempt."""

    attempt_id: str
    score: float
    passed: bool
    pass_score: int
    total: int
    correct_count: int
    questions: list[GradedQuestionOut]
    weak_objectives: list[dict]


@protected.post("/quiz/attempts/{attempt_id}/submit", response_model=GradedOut)
async def submit_quiz_attempt(
    attempt_id: uuid.UUID, body: SubmitIn, user: CurrentUser, db: Db
) -> GradedOut:
    try:
        result = await learning.grade_attempt(db, user, attempt_id, body.answers)
    except learning.LearningError as exc:
        raise _http(exc) from exc

    return GradedOut(
        attempt_id=str(result.attempt_id),
        score=result.score,
        passed=result.passed,
        pass_score=result.pass_score,
        total=result.total,
        correct_count=result.correct_count,
        questions=[
            GradedQuestionOut(
                id=q.code,
                stem=q.stem,
                level=q.level,
                objectives=q.objectives,
                given=q.given,
                correct=q.correct,
                is_correct=q.is_correct,
                explanation=q.explanation,
                options=q.options,
            )
            for q in result.questions
        ],
        weak_objectives=result.weak_objectives,
    )


# ------------------------------------------------------------ troubleshooting


class HypothesisIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class HypothesisOut(BaseModel):
    id: str
    submitted_at: datetime
    solution_unlocked: bool


@protected.post(
    "/topics/{slug}/troubleshooting/{code}/hypothesis",
    response_model=HypothesisOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_hypothesis(
    slug: str, code: str, body: HypothesisIn, user: CurrentUser, db: Db
) -> HypothesisOut:
    try:
        hypothesis = await learning.submit_hypothesis(db, user, slug, code, body.body)
    except learning.LearningError as exc:
        raise _http(exc) from exc
    return HypothesisOut(
        id=str(hypothesis.id),
        submitted_at=hypothesis.submitted_at,
        solution_unlocked=True,
    )


@router.get("/topics/{slug}/troubleshooting/{code}/solution")
async def troubleshooting_solution(slug: str, code: str, user: CurrentUser, db: Db) -> dict:
    """Gated. Returns 423 LockedError until a hypothesis has been submitted."""
    try:
        return await learning.reveal_solution(db, user, slug, code)
    except learning.LearningError as exc:
        raise _http(exc) from exc


# ------------------------------------------------------------------ dashboard


@router.get("/dashboard")
async def get_dashboard(user: CurrentUser, db: Db) -> dict:
    return await learning.dashboard(db, user)


router.include_router(protected)


class StepProgressOut(BaseModel):
    step_slug: str
    status: str


@protected.put("/topics/{slug}/steps/{step_slug}/progress", response_model=StepProgressOut)
async def set_step_progress(
    slug: str, step_slug: str, body: ProgressIn, user: CurrentUser, db: Db
) -> StepProgressOut:
    """Record progress against one screen of the course player.

    The player addresses steps by their outline slug; this resolves that to the
    entity the progress table actually keys on, so the frontend never has to
    know about content UUIDs.
    """
    from app.api.v1.curriculum import get_outline

    outline = await get_outline(slug, db)
    step = next((s for s in outline.steps if s.slug == step_slug), None)
    if step is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"step '{step_slug}' not found")

    await learning.set_progress(
        db,
        user,
        entity_type=step.entity_type,
        entity_id=uuid.UUID(step.entity_id),
        status=body.status,
    )

    # Finishing every step finishes the topic. Making the learner also click
    # "mark complete" on the topic would be a second, redundant action.
    if body.status == "completed":
        done = await learning.progress_map(db, user)
        finished = {str(key[1]) for key, row in done.items() if row.status == "completed"}
        if all(s.entity_id in finished for s in outline.steps):
            topic_id = await db.scalar(select(Topic.id).where(Topic.slug == slug))
            if topic_id is not None:
                await learning.set_progress(
                    db, user, entity_type="topic", entity_id=topic_id, status="completed"
                )

    return StepProgressOut(step_slug=step_slug, status=body.status)
