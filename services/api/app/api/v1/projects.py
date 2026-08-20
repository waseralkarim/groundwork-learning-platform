"""Projects and rubric-based self-review.

Three decisions worth stating, because each one is a place this could quietly
become dishonest or unsafe.

**The platform never fetches the artifact URL.** A learner submits a link to
their own repository or a running system. A server that follows a
user-supplied URL is a server-side request forgery primitive: point it at
`http://169.254.169.254/` or an internal address and it becomes a probe of
infrastructure the learner cannot otherwise reach. The URL is stored, shown back
to its owner, and never dereferenced. It is also validated to be http(s) so it
cannot smuggle `file://` or `javascript:` into a page.

**Every score requires evidence.** A criterion marked "excellent" with nothing
pointed at is an opinion, and the endpoint rejects it. This is the only lever
that makes self-review worth the learner's time.

**Self-review scores feed nothing.** They do not contribute to competence, they
do not unlock a certificate, and there is no code path from here to either.
Self-assessment that unlocks something stops being self-assessment on the day
someone wants the thing it unlocks.
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, optional_user
from app.db.session import get_session
from app.models.curriculum import Topic
from app.models.identity import User, UserProgress
from app.models.projects import Project, ProjectSubmission
from app.schemas.projects import (
    ProjectDetailOut,
    ProjectSummaryOut,
    RubricCriterionOut,
    SubmissionIn,
    SubmissionOut,
)
from app.services.learning import set_progress

router = APIRouter(tags=["projects"])

VALID_SCORES = {"inadequate", "adequate", "excellent"}
SCORE_POINTS = {"inadequate": 0, "adequate": 60, "excellent": 100}


@router.get("/projects", response_model=list[ProjectSummaryOut])
async def list_projects(
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectSummaryOut]:
    projects = list(await session.scalars(select(Project).order_by(Project.level, Project.title)))
    unlocked = await _completed_topic_ids(session, user)

    return [
        ProjectSummaryOut(
            slug=project.slug,
            title=project.title,
            level=project.level,
            estimated_hours=project.estimated_hours,
            summary=project.summary,
            requires_topics=list(project.requires_topics),
            unlocked=_is_unlocked(project, unlocked),
        )
        for project in projects
    ]


@router.get("/projects/{slug}", response_model=ProjectDetailOut)
async def get_project(
    slug: str,
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
) -> ProjectDetailOut:
    project = await session.scalar(select(Project).where(Project.slug == slug))
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="project not found")

    unlocked_ids = await _completed_topic_ids(session, user)
    unlocked = _is_unlocked(project, unlocked_ids)

    missing: list[str] = []
    if not unlocked:
        missing = await _missing_topic_titles(session, project, unlocked_ids)

    return ProjectDetailOut(
        slug=project.slug,
        title=project.title,
        level=project.level,
        estimated_hours=project.estimated_hours,
        summary=project.summary,
        # The brief is withheld until the topics are done, for the same reason a
        # topic's prerequisites are enforced: attempting this early teaches
        # frustration rather than the subject.
        brief=project.brief if unlocked else "",
        constraints=list(project.constraints) if unlocked else [],
        deliverables=list(project.deliverables) if unlocked else [],
        going_further=list(project.going_further) if unlocked else [],
        rubric=[RubricCriterionOut(**criterion) for criterion in project.rubric]
        if unlocked
        else [],
        requires_topics=list(project.requires_topics),
        unlocked=unlocked,
        missing_topics=missing,
    )


@router.get("/projects/{slug}/submissions", response_model=list[SubmissionOut])
async def my_submissions(
    slug: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[SubmissionOut]:
    project = await session.scalar(select(Project).where(Project.slug == slug))
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="project not found")

    rows = await session.scalars(
        select(ProjectSubmission)
        .where(
            ProjectSubmission.user_id == user.id,
            ProjectSubmission.project_id == project.id,
        )
        .order_by(ProjectSubmission.submitted_at.desc())
    )
    return [_submission_out(row) for row in rows]


@router.post(
    "/projects/{slug}/submissions",
    response_model=SubmissionOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit(
    slug: str,
    body: SubmissionIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> SubmissionOut:
    project = await session.scalar(select(Project).where(Project.slug == slug))
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="project not found")

    unlocked_ids = await _completed_topic_ids(session, user)
    if not _is_unlocked(project, unlocked_ids):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Finish the required topics before submitting this project.",
        )

    if body.artifact_url:
        parsed = urlparse(body.artifact_url)
        # http(s) only. The URL is never fetched, but it is rendered back as a
        # link, and `javascript:` in an href is a stored cross-site scripting
        # bug wearing a URL's clothes.
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="artifact_url must be an http or https URL",
            )

    rubric_ids = {criterion["id"] for criterion in project.rubric}
    seen: set[str] = set()
    for score in body.scores:
        if score.criterion_id not in rubric_ids:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"unknown rubric criterion '{score.criterion_id}'",
            )
        if score.criterion_id in seen:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"criterion '{score.criterion_id}' scored twice",
            )
        seen.add(score.criterion_id)
        if score.score not in VALID_SCORES:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"score must be one of {sorted(VALID_SCORES)}",
            )

    missing = rubric_ids - seen
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Every criterion needs a judgement, including the ones you did "
                f"badly on. Missing: {', '.join(sorted(missing))}."
            ),
        )

    weights = {criterion["id"]: criterion.get("weight", 1) for criterion in project.rubric}
    total_weight = sum(weights.values()) or 1
    self_score = round(
        sum(SCORE_POINTS[s.score] * weights[s.criterion_id] for s in body.scores) / total_weight
    )

    submission = ProjectSubmission(
        user_id=user.id,
        project_id=project.id,
        artifact_url=body.artifact_url,
        notes=body.notes,
        scores=[s.model_dump() for s in body.scores],
        self_score=self_score,
    )
    session.add(submission)
    await session.flush()

    # Progress is recorded — the learner did the work — but the *score* is not
    # passed here, and nothing in the competence model reads a project. See the
    # module docstring.
    #
    # Through the service rather than a bare insert: progress is unique per
    # (user, entity), so a second submission to the same project must update the
    # existing row rather than add another. Inserting directly worked for the
    # first submission and violated the constraint on the second.
    await set_progress(
        session,
        user,
        entity_type="project",
        entity_id=project.id,
        status="completed",
    )
    await session.commit()
    await session.refresh(submission)
    return _submission_out(submission)


# ------------------------------------------------------------------- helpers


async def _completed_topic_ids(session: AsyncSession, user: User | None) -> set:
    if user is None:
        return set()
    rows = await session.scalars(
        select(UserProgress.entity_id).where(
            UserProgress.user_id == user.id,
            UserProgress.entity_type == "topic",
            UserProgress.status == "completed",
        )
    )
    return set(rows)


def _is_unlocked(project: Project, completed_topic_ids: set) -> bool:
    from app.models.curriculum import content_uuid

    required = {content_uuid(topic_id) for topic_id in project.requires_topics}
    return required.issubset(completed_topic_ids)


async def _missing_topic_titles(
    session: AsyncSession, project: Project, completed_topic_ids: set
) -> list[str]:
    from app.models.curriculum import content_uuid

    missing_ids = [
        content_uuid(topic_id)
        for topic_id in project.requires_topics
        if content_uuid(topic_id) not in completed_topic_ids
    ]
    if not missing_ids:
        return []
    rows = await session.scalars(select(Topic.title).where(Topic.id.in_(missing_ids)))
    return list(rows)


def _submission_out(submission: ProjectSubmission) -> SubmissionOut:
    return SubmissionOut(
        id=str(submission.id),
        artifact_url=submission.artifact_url,
        notes=submission.notes,
        scores=submission.scores,
        self_score=submission.self_score,
        submitted_at=submission.submitted_at,
    )
