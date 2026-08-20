"""Curriculum tables — a projection of `content/` in git.

The central design decision lives here: **every primary key is a deterministic
UUIDv5 of the content's stable `id` string**, not a generated surrogate.

That means re-ingesting after a directory rename, a retitle or a reorder
produces the same keys, so a learner's progress rows still resolve. Content
platforms that key on a path or an autoincrement quietly orphan progress the
first time someone reorganises a folder, and nobody notices for six months.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

# Fixed namespace. Changing this value would re-key the entire curriculum and
# detach every progress record, so it is a constant, never a setting.
CONTENT_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")


def content_uuid(content_id: str) -> uuid.UUID:
    """Stable key for a piece of content, derived from its declared id."""
    return uuid.uuid5(CONTENT_NAMESPACE, content_id)


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True)


class LearningPath(Base, TimestampMixin):
    __tablename__ = "learning_paths"

    id: Mapped[uuid.UUID] = _pk()
    content_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    courses: Mapped[list[PathCourse]] = relationship(
        back_populates="path", cascade="all, delete-orphan", order_by="PathCourse.order"
    )


class PathCourse(Base):
    __tablename__ = "path_courses"

    path_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_paths.id", ondelete="CASCADE"), primary_key=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    path: Mapped[LearningPath] = relationship(back_populates="courses")
    course: Mapped[Course] = relationship()


class Course(Base, TimestampMixin):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = _pk()
    content_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(4), nullable=False)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    track: Mapped[str] = mapped_column(String(60), nullable=False)
    levels: Mapped[list[str]] = mapped_column(ARRAY(String(2)), nullable=False)
    estimated_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    modules: Mapped[list[Module]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="Module.order"
    )


class Module(Base, TimestampMixin):
    __tablename__ = "modules"

    id: Mapped[uuid.UUID] = _pk()
    content_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    course: Mapped[Course] = relationship(back_populates="modules")
    topics: Mapped[list[Topic]] = relationship(
        back_populates="module", cascade="all, delete-orphan", order_by="Topic.order"
    )

    __table_args__ = (UniqueConstraint("course_id", "slug", name="uq_modules_course_id_slug"),)


class Topic(Base, TimestampMixin):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = _pk()
    content_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    module_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("modules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    levels: Mapped[list[str]] = mapped_column(ARRAY(String(2)), nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="published")
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(80)), nullable=False, default=list)
    terminology: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    foreshadows: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    module: Mapped[Module] = relationship(back_populates="topics")
    lessons: Mapped[list[Lesson]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", order_by="Lesson.order"
    )
    objectives: Mapped[list[Objective]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", order_by="Objective.code"
    )
    labs: Mapped[list[Lab]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", order_by="Lab.order"
    )
    quiz: Mapped[Quiz | None] = relationship(
        back_populates="topic", cascade="all, delete-orphan", uselist=False
    )
    items: Mapped[list[TopicItem]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", order_by="TopicItem.order"
    )


class Objective(Base):
    __tablename__ = "objectives"

    id: Mapped[uuid.UUID] = _pk()
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    level: Mapped[str] = mapped_column(String(2), nullable=False)
    verb: Mapped[str] = mapped_column(String(30), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    assessed_by: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)

    topic: Mapped[Topic] = relationship(back_populates="objectives")

    __table_args__ = (UniqueConstraint("topic_id", "code", name="uq_objectives_topic_id_code"),)


class Prerequisite(Base):
    __tablename__ = "prerequisites"

    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    requires_topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    hardness: Mapped[str] = mapped_column(String(16), nullable=False, default="required")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[uuid.UUID] = _pk()
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="explain")
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    topic: Mapped[Topic] = relationship(back_populates="lessons")

    __table_args__ = (UniqueConstraint("topic_id", "section", name="uq_lessons_topic_id_section"),)


class Lab(Base):
    __tablename__ = "labs"

    id: Mapped[uuid.UUID] = _pk()
    content_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    image: Mapped[str] = mapped_column(String(120), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    objectives: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    # Steps, checks and solution. Read whole, never queried into — JSONB is the
    # right shape until the lab broker needs to index it, which it does not.
    spec: Mapped[dict] = mapped_column(JSONB, nullable=False)

    topic: Mapped[Topic] = relationship(back_populates="labs")


class TopicItem(Base):
    """Exercises, troubleshooting scenarios, interview questions, assessments.

    One table with a discriminator rather than four near-identical ones: they
    share a lifecycle, are always fetched by topic, and none of them is queried
    by its internal structure. Splitting them would buy nothing but four joins.
    """

    __tablename__ = "topic_items"

    id: Mapped[uuid.UUID] = _pk()
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    content_id: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[str | None] = mapped_column(String(2), nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    objectives: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    # Public half — safe to serve to anyone.
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Answers, root causes, rubrics, model answers. Never leaves the API without
    # an explicit gate; the public response models have no field for it.
    solution: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    topic: Mapped[Topic] = relationship(back_populates="items")

    __table_args__ = (
        UniqueConstraint("topic_id", "kind", "content_id", name="uq_topic_items_identity"),
        Index("ix_topic_items_topic_kind", "topic_id", "kind"),
    )


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[uuid.UUID] = _pk()
    content_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    pass_score: Mapped[int] = mapped_column(Integer, nullable=False, default=70)

    topic: Mapped[Topic] = relationship(back_populates="quiz")
    questions: Mapped[list[QuizQuestion]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan", order_by="QuizQuestion.order"
    )


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[uuid.UUID] = _pk()
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    level: Mapped[str] = mapped_column(String(2), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    objectives: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    # Shown only after an attempt is graded.
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    quiz: Mapped[Quiz] = relationship(back_populates="questions")
    options: Mapped[list[QuizOption]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="QuizOption.code"
    )

    __table_args__ = (UniqueConstraint("quiz_id", "code", name="uq_quiz_questions_quiz_id_code"),)


class QuizOption(Base):
    __tablename__ = "quiz_options"

    id: Mapped[uuid.UUID] = _pk()
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(2), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # The answer key. Excluded from every public response model by construction,
    # not by remembering to strip it.
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    question: Mapped[QuizQuestion] = relationship(back_populates="options")

    __table_args__ = (
        UniqueConstraint("question_id", "code", name="uq_quiz_options_question_id_code"),
    )


class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"

    id: Mapped[uuid.UUID] = _pk()
    term: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    defined_in_topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
