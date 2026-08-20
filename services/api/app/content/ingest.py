"""Ingests a validated content tree into PostgreSQL.

Two properties matter more than anything else here.

**Idempotence.** Running ingest twice against unchanged content must produce an
identical database. Every write is an upsert keyed on the content's declared id.

**Stability under churn.** Renaming a directory, retitling a topic or reordering
a module must not change any primary key, because progress rows point at those
keys. This is guaranteed by `content_uuid()`, not by care.

`tests/test_ingest_integration.py` asserts both.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content import search_index
from app.content.loader import ContentTree, LoadedTopic
from app.core.logging import get_logger
from app.core.metrics import record_ingest
from app.models.content import ContentVersion
from app.models.curriculum import (
    Course,
    GlossaryTerm,
    Lab,
    LearningPath,
    Lesson,
    Module,
    Objective,
    PathCourse,
    Prerequisite,
    Quiz,
    QuizOption,
    QuizQuestion,
    Topic,
    TopicItem,
    content_uuid,
)
from app.models.projects import Project as ProjectRow

log = get_logger(__name__)


@dataclass
class IngestResult:
    paths: int = 0
    courses: int = 0
    modules: int = 0
    topics: int = 0
    lessons: int = 0
    labs: int = 0
    questions: int = 0
    items: int = 0
    terms: int = 0
    projects: int = 0
    search_rows: int = 0
    version_id: str | None = None

    def summary(self) -> str:
        return (
            f"{self.paths} paths, {self.courses} courses, {self.modules} modules, "
            f"{self.topics} topics, {self.lessons} lessons, {self.labs} labs, "
            f"{self.questions} quiz questions, {self.items} items, {self.terms} glossary terms, "
            f"{self.projects} projects, "
            f"{self.search_rows} search rows"
        )


def _hash(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


async def _upsert(session: AsyncSession, model: type, pk, **values):
    """Fetch-or-create by primary key, then overwrite the mutable columns.

    Deliberately not `INSERT ... ON CONFLICT`: the identity map keeps the
    relationship cascades below coherent, and content volumes are small enough
    that the round trips do not matter.
    """
    instance = await session.get(model, pk)
    if instance is None:
        instance = model(id=pk, **values)
        session.add(instance)
        return instance
    for key, value in values.items():
        setattr(instance, key, value)
    return instance


class Ingester:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.result = IngestResult()

    async def run(self, tree: ContentTree, git_sha: str = "unknown") -> IngestResult:
        started = time.perf_counter()
        ok = False
        try:
            result = await self._run(tree, git_sha)
            ok = True
            return result
        finally:
            record_ingest(time.perf_counter() - started, ok=ok)

    async def _run(self, tree: ContentTree, git_sha: str = "unknown") -> IngestResult:
        await self._prune_removed(tree)

        for course in tree.courses:
            await self._ingest_course(course)

        # Prerequisites and paths reference topics/courses by id, so they land
        # after everything they point at exists.
        await self.session.flush()
        await self._ingest_prerequisites(tree)
        await self._ingest_paths(tree)
        await self._ingest_projects(tree)
        await self._record_version(tree, git_sha)

        # Last, and inside the same transaction: an index that can be newer or
        # older than the content it describes is worse than no index.
        self.result.search_rows = await search_index.rebuild(self.session)

        await self.session.commit()

        log.info("content_ingested", summary=self.result.summary(), git_sha=git_sha)
        return self.result

    # ------------------------------------------------------------------ prune

    async def _prune_removed(self, tree: ContentTree) -> None:
        """Delete database rows whose content no longer exists in git.

        Cascades remove their children. Progress rows are untouched — they point
        at stable ids and will resolve again if the content returns.
        """
        live_courses = {content_uuid(c.course.id) for c in tree.courses}
        live_modules = {content_uuid(m.module.id) for c in tree.courses for m in c.modules}
        live_topics = {content_uuid(t.topic.id) for t in tree.all_topics()}
        live_paths = {content_uuid(p.id) for p in tree.paths}

        for model, live in (
            (Topic, live_topics),
            (Module, live_modules),
            (Course, live_courses),
            (LearningPath, live_paths),
        ):
            existing = set((await self.session.scalars(select(model.id))).all())
            stale = existing - live
            if stale:
                await self.session.execute(delete(model).where(model.id.in_(stale)))
                log.info("content_pruned", model=model.__name__, count=len(stale))

    # ----------------------------------------------------------------- course

    async def _ingest_course(self, loaded) -> None:
        course = loaded.course
        await _upsert(
            self.session,
            Course,
            content_uuid(course.id),
            content_id=course.id,
            slug=course.slug,
            code=course.code,
            title=course.title,
            summary=course.summary,
            track=course.track,
            levels=[level.value for level in course.levels],
            estimated_hours=course.estimated_hours,
            order=course.order,
        )
        self.result.courses += 1
        # Autoflush is off on this session, so parents must be flushed before
        # their children are added — otherwise the children's foreign keys point
        # at rows that do not exist yet.
        await self.session.flush()

        for module in loaded.modules:
            await self._ingest_module(module, course.id)

    async def _ingest_module(self, loaded, course_id: str) -> None:
        module = loaded.module
        await _upsert(
            self.session,
            Module,
            content_uuid(module.id),
            content_id=module.id,
            course_id=content_uuid(course_id),
            slug=module.slug,
            title=module.title,
            summary=module.summary,
            order=module.order,
        )
        self.result.modules += 1
        await self.session.flush()

        for topic in loaded.topics:
            await self._ingest_topic(topic, module.id)

    # ------------------------------------------------------------------ topic

    async def _ingest_topic(self, loaded: LoadedTopic, module_id: str) -> None:
        topic = loaded.topic
        topic_pk = content_uuid(topic.id)

        body_hash = _hash(*(lesson.body for lesson in loaded.lessons), topic.title, topic.summary)

        await _upsert(
            self.session,
            Topic,
            topic_pk,
            content_id=topic.id,
            module_id=content_uuid(module_id),
            slug=topic.slug,
            title=topic.title,
            summary=topic.summary,
            order=topic.order,
            levels=[level.value for level in topic.levels],
            estimated_minutes=topic.estimated_minutes,
            status=topic.status,
            tags=list(topic.tags),
            terminology=[term.model_dump() for term in topic.terminology],
            foreshadows=list(topic.foreshadows),
            content_hash=body_hash,
        )
        self.result.topics += 1
        await self.session.flush()

        await self._replace_children(topic_pk, loaded)
        await self.session.flush()

    async def _replace_children(self, topic_pk, loaded: LoadedTopic) -> None:
        """Children are replaced wholesale.

        Their identity is positional within a topic, so diffing them buys
        nothing and risks leaving orphans behind. Progress attaches to topics,
        labs and quiz questions by *content id*, all of which are reconstructed
        with the same deterministic keys.
        """
        topic = loaded.topic

        await self.session.execute(delete(Objective).where(Objective.topic_id == topic_pk))
        for objective in topic.objectives:
            self.session.add(
                Objective(
                    id=content_uuid(f"{topic.id}#{objective.id}"),
                    topic_id=topic_pk,
                    code=objective.id,
                    level=objective.level.value,
                    verb=objective.verb,
                    statement=objective.statement,
                    assessed_by=list(objective.assessed_by),
                )
            )

        await self.session.execute(delete(Lesson).where(Lesson.topic_id == topic_pk))
        for lesson in loaded.lessons:
            self.session.add(
                Lesson(
                    id=content_uuid(f"{topic.id}#lesson#{lesson.frontmatter.section}"),
                    topic_id=topic_pk,
                    section=lesson.frontmatter.section,
                    title=lesson.frontmatter.title,
                    mode=lesson.frontmatter.mode.value,
                    order=lesson.frontmatter.order,
                    body_md=lesson.body,
                    content_hash=_hash(lesson.body),
                )
            )
            self.result.lessons += 1

        await self.session.execute(delete(Lab).where(Lab.topic_id == topic_pk))
        for index, lab in enumerate(loaded.labs, start=1):
            self.session.add(
                Lab(
                    id=content_uuid(lab.id),
                    content_id=lab.id,
                    topic_id=topic_pk,
                    slug=lab.id.rsplit(".", 1)[-1],
                    title=lab.title,
                    type=lab.type,
                    tier=lab.tier,
                    image=lab.image,
                    duration_minutes=lab.duration_minutes,
                    order=index,
                    objectives=list(lab.objectives),
                    spec=lab.model_dump(mode="json"),
                )
            )
            self.result.labs += 1

        await self._replace_quiz(topic_pk, loaded)
        await self._replace_items(topic_pk, loaded)

        for term in topic.terminology:
            await _upsert(
                self.session,
                GlossaryTerm,
                content_uuid(f"glossary#{term.term.lower()}"),
                term=term.term,
                definition=term.definition,
                defined_in_topic_id=topic_pk,
            )
            self.result.terms += 1

    async def _replace_quiz(self, topic_pk, loaded: LoadedTopic) -> None:
        await self.session.execute(delete(Quiz).where(Quiz.topic_id == topic_pk))
        quiz = loaded.quiz
        if not quiz:
            return

        quiz_pk = content_uuid(quiz.id)
        self.session.add(
            Quiz(id=quiz_pk, content_id=quiz.id, topic_id=topic_pk, pass_score=quiz.pass_score)
        )

        for index, question in enumerate(quiz.questions, start=1):
            question_pk = content_uuid(f"{quiz.id}#{question.id}")
            self.session.add(
                QuizQuestion(
                    id=question_pk,
                    quiz_id=quiz_pk,
                    code=question.id,
                    type=question.type,
                    level=question.level.value,
                    order=index,
                    stem=question.stem,
                    objectives=list(question.objectives),
                    explanation=question.explanation,
                )
            )
            self.result.questions += 1

            for option in question.options:
                self.session.add(
                    QuizOption(
                        id=content_uuid(f"{quiz.id}#{question.id}#{option.id}"),
                        question_id=question_pk,
                        code=option.id,
                        text=option.text,
                        is_correct=option.correct,
                        note=option.note,
                    )
                )

    async def _replace_items(self, topic_pk, loaded: LoadedTopic) -> None:
        await self.session.execute(delete(TopicItem).where(TopicItem.topic_id == topic_pk))
        topic_id = loaded.topic.id

        def add(kind: str, content_id: str, title: str, level, order, objectives, public, private):
            self.session.add(
                TopicItem(
                    id=content_uuid(f"{topic_id}#{kind}#{content_id}"),
                    topic_id=topic_pk,
                    kind=kind,
                    content_id=content_id,
                    title=title,
                    level=level,
                    order=order,
                    objectives=list(objectives),
                    payload=public,
                    solution=private,
                )
            )
            self.result.items += 1

        if loaded.exercises:
            for index, exercise in enumerate(loaded.exercises.exercises, start=1):
                data = exercise.model_dump(mode="json")
                private = {"answer": data.pop("answer"), "explanation": data.pop("explanation")}
                add(
                    "exercise",
                    exercise.id,
                    exercise.title,
                    exercise.level.value,
                    index,
                    exercise.objectives,
                    data,
                    private,
                )

        for index, scenario in enumerate(loaded.troubleshooting, start=1):
            data = scenario.model_dump(mode="json")
            private = {
                "root_cause": data.pop("root_cause"),
                "method": data.pop("method"),
                "resolution": data.pop("resolution"),
                "hints": data.pop("hints", []),
            }
            add(
                "troubleshooting",
                scenario.id,
                scenario.title,
                scenario.level.value,
                index,
                scenario.objectives,
                data,
                private,
            )

        if loaded.interview:
            for index, question in enumerate(loaded.interview.questions, start=1):
                data = question.model_dump(mode="json")
                private = {
                    "model_answer": data.pop("model_answer"),
                    "signal": data.pop("signal"),
                }
                add(
                    "interview",
                    question.id,
                    question.question[:200],
                    question.level.value,
                    index,
                    [],
                    data,
                    private,
                )

        if loaded.assessment:
            for index, part in enumerate(loaded.assessment.parts, start=1):
                data = part.model_dump(mode="json")
                private = {
                    "rubric": data.pop("rubric"),
                    "model_answer": data.pop("model_answer"),
                    "common_failures": data.pop("common_failures", []),
                }
                add(
                    "assessment",
                    part.id,
                    part.title,
                    None,
                    index,
                    part.objectives,
                    data,
                    private,
                )

    # ------------------------------------------------------------ references

    async def _ingest_prerequisites(self, tree: ContentTree) -> None:
        await self.session.execute(delete(Prerequisite))
        for loaded in tree.all_topics():
            for prerequisite in loaded.topic.prerequisites:
                self.session.add(
                    Prerequisite(
                        topic_id=content_uuid(loaded.topic.id),
                        requires_topic_id=content_uuid(prerequisite.topic),
                        hardness=prerequisite.hardness,
                    )
                )

    async def _ingest_paths(self, tree: ContentTree) -> None:
        await self.session.execute(delete(PathCourse))
        for path in tree.paths:
            await _upsert(
                self.session,
                LearningPath,
                content_uuid(path.id),
                content_id=path.id,
                slug=path.slug,
                title=path.title,
                summary=path.summary,
            )
            self.result.paths += 1
            await self.session.flush()

            for entry in path.courses:
                self.session.add(
                    PathCourse(
                        path_id=content_uuid(path.id),
                        course_id=content_uuid(entry.course),
                        order=entry.order,
                    )
                )

    async def _ingest_projects(self, tree: ContentTree) -> None:
        """Projects are keyed on their content id, like everything else.

        Upserted rather than replaced so a learner's submissions — which point at
        the project row — survive a retitle or a rubric revision. A rubric that
        changes after someone has submitted against it is a real event, and their
        old submission keeps the scores they gave, not the new criteria.
        """
        for project in tree.projects:
            await _upsert(
                self.session,
                ProjectRow,
                content_uuid(project.id),
                content_id=project.id,
                slug=project.slug,
                title=project.title,
                level=project.level.value,
                estimated_hours=project.estimated_hours,
                summary=project.summary,
                brief=project.brief,
                requires_topics=list(project.requires_topics),
                constraints=list(project.constraints),
                deliverables=list(project.deliverables),
                rubric=[criterion.model_dump(mode="json") for criterion in project.rubric],
                going_further=list(project.going_further),
            )
            self.result.projects += 1
        await self.session.flush()

    async def _record_version(self, tree: ContentTree, git_sha: str) -> None:
        existing = await self.session.scalars(
            select(ContentVersion).where(ContentVersion.is_current)
        )
        for version in existing:
            version.is_current = False
        await self.session.flush()

        version = ContentVersion(
            git_sha=git_sha[:40],
            ingested_at=datetime.now(UTC),
            is_current=True,
            topic_count=len(tree.all_topics()),
            notes=self.result.summary(),
        )
        self.session.add(version)
        await self.session.flush()
        self.result.version_id = str(version.id)


async def ingest(
    session: AsyncSession, tree: ContentTree, git_sha: str = "unknown"
) -> IngestResult:
    return await Ingester(session).run(tree, git_sha)
