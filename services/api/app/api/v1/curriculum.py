"""Curriculum read API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_session
from app.models.content import ContentVersion
from app.models.curriculum import (
    Course,
    Lab,
    LearningPath,
    Module,
    Prerequisite,
    Quiz,
    QuizQuestion,
    Topic,
    TopicItem,
)
from app.schemas.curriculum import (
    AssessmentPartOut,
    CourseDetailOut,
    CourseSummaryOut,
    ExerciseOut,
    InterviewQuestionOut,
    LabDetailOut,
    LabSummaryOut,
    LessonOut,
    ModuleOut,
    ObjectiveOut,
    OutlineStepOut,
    PathOut,
    PrerequisiteOut,
    QuizOptionOut,
    QuizOut,
    QuizQuestionOut,
    RoadmapCourseOut,
    RoadmapModuleOut,
    RoadmapOut,
    RoadmapTopicOut,
    TermOut,
    TopicDetailOut,
    TopicNavOut,
    TopicOutlineOut,
    TopicSummaryOut,
    TroubleshootingOut,
)

router = APIRouter(tags=["curriculum"])

_FULL_COURSE = (selectinload(Course.modules).selectinload(Module.topics),)


def _not_found(what: str, slug: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=f"{what} '{slug}' not found")


def _course_summary(course: Course) -> CourseSummaryOut:
    return CourseSummaryOut(
        slug=course.slug,
        code=course.code,
        title=course.title,
        summary=course.summary,
        track=course.track,
        levels=course.levels,
        estimated_hours=course.estimated_hours,
        order=course.order,
        topic_count=sum(len(module.topics) for module in course.modules),
    )


@router.get("/roadmap", response_model=RoadmapOut)
async def roadmap(session: AsyncSession = Depends(get_session)) -> RoadmapOut:
    """The whole curriculum in one call — the landing page's only request."""
    path = await session.scalar(
        select(LearningPath)
        .options(selectinload(LearningPath.courses))
        .order_by(LearningPath.slug)
        .limit(1)
    )
    if path is None:
        raise _not_found("learning path", "default")

    course_ids = [entry.course_id for entry in path.courses]
    order_by_id = {entry.course_id: entry.order for entry in path.courses}

    courses = list(
        await session.scalars(
            select(Course).where(Course.id.in_(course_ids)).options(*_FULL_COURSE)
        )
    )
    courses.sort(key=lambda c: order_by_id.get(c.id, c.order))

    version = await session.scalar(select(ContentVersion).where(ContentVersion.is_current))

    out_courses: list[RoadmapCourseOut] = []
    total = published = 0

    for course in courses:
        modules: list[RoadmapModuleOut] = []
        course_topics = 0
        course_published = 0

        for module in course.modules:
            topics = [
                RoadmapTopicOut(
                    slug=t.slug,
                    title=t.title,
                    levels=t.levels,
                    estimated_minutes=t.estimated_minutes,
                    status=t.status,
                )
                for t in module.topics
                if t.status != "retired"
            ]
            course_topics += len(topics)
            course_published += sum(1 for t in topics if t.status == "published")
            modules.append(RoadmapModuleOut(slug=module.slug, title=module.title, topics=topics))

        total += course_topics
        published += course_published

        out_courses.append(
            RoadmapCourseOut(
                slug=course.slug,
                code=course.code,
                title=course.title,
                summary=course.summary,
                track=course.track,
                levels=course.levels,
                estimated_hours=course.estimated_hours,
                modules=modules,
                topic_count=course_topics,
                published_topic_count=course_published,
            )
        )

    return RoadmapOut(
        path_slug=path.slug,
        title=path.title,
        summary=path.summary,
        courses=out_courses,
        total_topics=total,
        published_topics=published,
        content_version=version.git_sha[:8] if version else None,
        ingested_at=version.ingested_at if version else None,
    )


@router.get("/paths/{slug}", response_model=PathOut)
async def get_path(slug: str, session: AsyncSession = Depends(get_session)) -> PathOut:
    path = await session.scalar(
        select(LearningPath)
        .where(LearningPath.slug == slug)
        .options(selectinload(LearningPath.courses))
    )
    if path is None:
        raise _not_found("learning path", slug)

    entries = sorted(path.courses, key=lambda e: e.order)
    courses = []
    for entry in entries:
        course = await session.get(Course, entry.course_id, options=_FULL_COURSE)
        if course is not None:
            courses.append(_course_summary(course))
    return PathOut(slug=path.slug, title=path.title, summary=path.summary, courses=courses)


@router.get("/courses/{slug}", response_model=CourseDetailOut)
async def get_course(slug: str, session: AsyncSession = Depends(get_session)) -> CourseDetailOut:
    course = await session.scalar(select(Course).where(Course.slug == slug).options(*_FULL_COURSE))
    if course is None:
        raise _not_found("course", slug)

    return CourseDetailOut(
        slug=course.slug,
        code=course.code,
        title=course.title,
        summary=course.summary,
        track=course.track,
        levels=course.levels,
        estimated_hours=course.estimated_hours,
        order=course.order,
        topic_count=sum(len(m.topics) for m in course.modules),
        modules=[
            ModuleOut(
                slug=module.slug,
                title=module.title,
                summary=module.summary,
                order=module.order,
                topics=[TopicSummaryOut.model_validate(t) for t in module.topics],
            )
            for module in course.modules
        ],
    )


async def _load_topic(session: AsyncSession, slug: str) -> Topic:
    topic = await session.scalar(
        select(Topic)
        .where(Topic.slug == slug)
        .options(
            selectinload(Topic.lessons),
            selectinload(Topic.objectives),
            selectinload(Topic.labs),
            selectinload(Topic.items),
            selectinload(Topic.module).selectinload(Module.course),
            selectinload(Topic.module).selectinload(Module.topics),
        )
    )
    if topic is None:
        raise _not_found("topic", slug)
    return topic


@router.get("/topics/{slug}", response_model=TopicDetailOut)
async def get_topic(slug: str, session: AsyncSession = Depends(get_session)) -> TopicDetailOut:
    topic = await _load_topic(session, slug)
    module = topic.module
    course = module.course

    siblings = sorted(module.topics, key=lambda t: t.order)
    position = next((i for i, t in enumerate(siblings) if t.id == topic.id), 0)
    previous = siblings[position - 1] if position > 0 else None
    following = siblings[position + 1] if position + 1 < len(siblings) else None

    prerequisite_rows = list(
        await session.execute(
            select(Prerequisite, Topic)
            .join(Topic, Topic.id == Prerequisite.requires_topic_id)
            .where(Prerequisite.topic_id == topic.id)
        )
    )

    quiz_id = await session.scalar(select(Quiz.id).where(Quiz.topic_id == topic.id))
    counts = dict.fromkeys(("exercise", "troubleshooting", "interview", "assessment"), 0)
    for item in topic.items:
        if item.kind in counts:
            counts[item.kind] += 1

    return TopicDetailOut(
        slug=topic.slug,
        title=topic.title,
        summary=topic.summary,
        levels=topic.levels,
        estimated_minutes=topic.estimated_minutes,
        status=topic.status,
        tags=topic.tags,
        terminology=[TermOut(**term) for term in topic.terminology],
        foreshadows=topic.foreshadows,
        course=TopicNavOut(slug=course.slug, title=course.title),
        module=TopicNavOut(slug=module.slug, title=module.title),
        previous=TopicNavOut(slug=previous.slug, title=previous.title) if previous else None,
        next=TopicNavOut(slug=following.slug, title=following.title) if following else None,
        objectives=[ObjectiveOut.model_validate(o) for o in topic.objectives],
        prerequisites=[
            PrerequisiteOut(slug=required.slug, title=required.title, hardness=link.hardness)
            for link, required in prerequisite_rows
        ],
        lessons=[LessonOut.model_validate(lesson) for lesson in topic.lessons],
        labs=[LabSummaryOut.model_validate(lab) for lab in topic.labs],
        has_quiz=quiz_id is not None,
        exercise_count=counts["exercise"],
        troubleshooting_count=counts["troubleshooting"],
        interview_count=counts["interview"],
        assessment_part_count=counts["assessment"],
    )


@router.get("/topics/{slug}/quiz", response_model=QuizOut)
async def get_quiz(slug: str, session: AsyncSession = Depends(get_session)) -> QuizOut:
    """Serves the quiz without its answer key.

    `QuizOptionOut` has no `is_correct` field and `QuizQuestionOut` has no
    `explanation`, so the key cannot leak through this endpoint even by mistake.
    Grading happens server-side in Phase 2.
    """
    topic_id = await session.scalar(select(Topic.id).where(Topic.slug == slug))
    if topic_id is None:
        raise _not_found("topic", slug)

    quiz = await session.scalar(
        select(Quiz)
        .where(Quiz.topic_id == topic_id)
        .options(selectinload(Quiz.questions).selectinload(QuizQuestion.options))
    )
    if quiz is None:
        raise _not_found("quiz for topic", slug)

    return QuizOut(
        topic_slug=slug,
        pass_score=quiz.pass_score,
        question_count=len(quiz.questions),
        questions=[
            QuizQuestionOut(
                id=question.code,
                type=question.type,
                level=question.level,
                stem=question.stem,
                options=[QuizOptionOut(id=o.code, text=o.text) for o in question.options],
            )
            for question in quiz.questions
        ],
    )


@router.get("/topics/{slug}/labs/{lab_slug}", response_model=LabDetailOut)
async def get_lab(
    slug: str, lab_slug: str, session: AsyncSession = Depends(get_session)
) -> LabDetailOut:
    topic_id = await session.scalar(select(Topic.id).where(Topic.slug == slug))
    if topic_id is None:
        raise _not_found("topic", slug)

    lab = await session.scalar(select(Lab).where(Lab.topic_id == topic_id, Lab.slug == lab_slug))
    if lab is None:
        raise _not_found("lab", lab_slug)

    spec = lab.spec
    # Steps keep their instructions and hints; `solution` and the verify
    # internals stay server-side until the learner asks or the check runs.
    steps = [
        {"id": step["id"], "instruction": step["instruction"], "hint": step.get("hint")}
        for step in spec.get("steps", [])
    ]

    return LabDetailOut(
        slug=lab.slug,
        title=lab.title,
        type=lab.type,
        tier=lab.tier,
        image=lab.image,
        duration_minutes=lab.duration_minutes,
        objectives=lab.objectives,
        intro=spec.get("intro", ""),
        steps=steps,
    )


async def _items(session: AsyncSession, slug: str, kind: str) -> list[TopicItem]:
    topic_id = await session.scalar(select(Topic.id).where(Topic.slug == slug))
    if topic_id is None:
        raise _not_found("topic", slug)
    return list(
        await session.scalars(
            select(TopicItem)
            .where(TopicItem.topic_id == topic_id, TopicItem.kind == kind)
            .order_by(TopicItem.order)
        )
    )


@router.get("/topics/{slug}/exercises", response_model=list[ExerciseOut])
async def get_exercises(
    slug: str, session: AsyncSession = Depends(get_session)
) -> list[ExerciseOut]:
    return [ExerciseOut(**item.payload) for item in await _items(session, slug, "exercise")]


@router.get("/topics/{slug}/troubleshooting", response_model=list[TroubleshootingOut])
async def get_troubleshooting(
    slug: str, session: AsyncSession = Depends(get_session)
) -> list[TroubleshootingOut]:
    scenarios = await _items(session, slug, "troubleshooting")
    return [
        TroubleshootingOut(
            id=item.content_id,
            title=item.payload["title"],
            level=item.payload["level"],
            reveal_policy=item.payload["reveal_policy"],
            situation=item.payload["situation"],
            symptoms=item.payload["symptoms"],
            artifacts=item.payload["artifacts"],
            diagnostic_questions=item.payload["diagnostic_questions"],
        )
        for item in scenarios
    ]


@router.get("/topics/{slug}/interview", response_model=list[InterviewQuestionOut])
async def get_interview(
    slug: str, session: AsyncSession = Depends(get_session)
) -> list[InterviewQuestionOut]:
    return [
        InterviewQuestionOut(
            id=item.payload["id"],
            level=item.payload["level"],
            question=item.payload["question"],
            follow_ups=item.payload.get("follow_ups", []),
        )
        for item in await _items(session, slug, "interview")
    ]


@router.get("/topics/{slug}/assessment", response_model=list[AssessmentPartOut])
async def get_assessment(
    slug: str, session: AsyncSession = Depends(get_session)
) -> list[AssessmentPartOut]:
    return [
        AssessmentPartOut(
            id=item.payload["id"],
            title=item.payload["title"],
            kind=item.payload["kind"],
            prompt=item.payload["prompt"],
        )
        for item in await _items(session, slug, "assessment")
    ]


@router.get("/topics/{slug}/outline", response_model=TopicOutlineOut)
async def get_outline(slug: str, session: AsyncSession = Depends(get_session)) -> TopicOutlineOut:
    """A topic as an ordered sequence of screens.

    The order is pedagogical, not structural: read, then do, then be tested.
    Lessons come in authored order, then labs, exercises, troubleshooting, the
    quiz, and finally the assessment.
    """
    topic = await _load_topic(session, slug)
    steps: list[OutlineStepOut] = []

    for lesson in sorted(topic.lessons, key=lambda item: item.order):
        steps.append(
            OutlineStepOut(
                slug=f"read-{lesson.section}",
                kind="lesson",
                title=lesson.title,
                subtitle=lesson.mode,
                entity_type="lesson",
                entity_id=str(lesson.id),
            )
        )

    for lab in sorted(topic.labs, key=lambda item: item.order):
        steps.append(
            OutlineStepOut(
                slug=f"lab-{lab.slug}",
                kind="lab",
                title=lab.title,
                subtitle=lab.type,
                entity_type="lab",
                entity_id=str(lab.id),
                estimated_minutes=lab.duration_minutes,
            )
        )

    ordered_kinds = ("exercise", "troubleshooting", "interview", "assessment")
    labels = {
        "exercise": "Exercises",
        "troubleshooting": "Troubleshooting",
        "interview": "Interview questions",
        "assessment": "Assessment",
    }
    for kind in ordered_kinds:
        items = [item for item in topic.items if item.kind == kind]
        if not items:
            continue

        if kind == "troubleshooting":
            # Each scenario is its own screen — they are the hardest thing in a
            # topic and deserve undivided attention.
            for item in sorted(items, key=lambda i: i.order):
                steps.append(
                    OutlineStepOut(
                        slug=f"diagnose-{item.content_id.rsplit('.', 1)[-1]}",
                        kind="troubleshooting",
                        title=item.title,
                        subtitle="diagnose",
                        entity_type="troubleshooting",
                        entity_id=str(item.id),
                        level=item.level,
                    )
                )
            continue

        first = sorted(items, key=lambda i: i.order)[0]
        steps.append(
            OutlineStepOut(
                slug=kind,
                kind=kind,
                title=labels[kind],
                subtitle=f"{len(items)} item{'s' if len(items) > 1 else ''}",
                entity_type=kind,
                entity_id=str(first.id),
            )
        )

    quiz_id = await session.scalar(select(Quiz.id).where(Quiz.topic_id == topic.id))
    if quiz_id is not None:
        # The quiz sits before the assessment: it is the cheap check, the
        # assessment is the gate.
        index = next((i for i, s in enumerate(steps) if s.kind == "assessment"), len(steps))
        steps.insert(
            index,
            OutlineStepOut(
                slug="quiz",
                kind="quiz",
                title="Quiz",
                subtitle="15 questions",
                entity_type="quiz",
                entity_id=str(quiz_id),
            ),
        )

    return TopicOutlineOut(
        topic_slug=topic.slug,
        topic_title=topic.title,
        course=TopicNavOut(slug=topic.module.course.slug, title=topic.module.course.title),
        module=TopicNavOut(slug=topic.module.slug, title=topic.module.title),
        estimated_minutes=topic.estimated_minutes,
        steps=steps,
    )
