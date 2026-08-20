"""Public API response models.

The security property that matters most in this file: **there is no field for an
answer key anywhere in it.**

`QuizQuestionOut` has no `is_correct`. `TroubleshootingOut` has no `root_cause`.
`AssessmentPartOut` has no `model_answer`. Leaking one is therefore not a matter
of remembering to strip it — it would require adding a field, which is a
reviewable change. This is the difference between a control and a habit.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TermOut(ApiModel):
    term: str
    definition: str


class ObjectiveOut(ApiModel):
    code: str
    level: str
    verb: str
    statement: str


class PrerequisiteOut(ApiModel):
    slug: str
    title: str
    hardness: str


class LessonOut(ApiModel):
    section: str
    title: str
    mode: str
    order: int
    body_md: str


class LabSummaryOut(ApiModel):
    slug: str
    title: str
    type: str
    tier: int
    duration_minutes: int
    objectives: list[str]


class TopicSummaryOut(ApiModel):
    slug: str
    title: str
    summary: str
    order: int
    levels: list[str]
    estimated_minutes: int
    status: str
    tags: list[str]


class ModuleOut(ApiModel):
    slug: str
    title: str
    summary: str
    order: int
    topics: list[TopicSummaryOut]


class CourseSummaryOut(ApiModel):
    slug: str
    code: str
    title: str
    summary: str
    track: str
    levels: list[str]
    estimated_hours: int
    order: int
    topic_count: int = 0


class CourseDetailOut(CourseSummaryOut):
    modules: list[ModuleOut]


class PathOut(ApiModel):
    slug: str
    title: str
    summary: str
    courses: list[CourseSummaryOut]


class TopicNavOut(ApiModel):
    slug: str
    title: str


class TopicDetailOut(ApiModel):
    slug: str
    title: str
    summary: str
    levels: list[str]
    estimated_minutes: int
    status: str
    tags: list[str]
    terminology: list[TermOut]
    foreshadows: list[str]

    course: TopicNavOut
    module: TopicNavOut
    previous: TopicNavOut | None = None
    next: TopicNavOut | None = None

    objectives: list[ObjectiveOut]
    prerequisites: list[PrerequisiteOut]
    lessons: list[LessonOut]
    labs: list[LabSummaryOut]

    has_quiz: bool
    exercise_count: int
    troubleshooting_count: int
    interview_count: int
    assessment_part_count: int


# ------------------------------------------------------------------------ quiz


class QuizOptionOut(ApiModel):
    """Note the absence of `is_correct` and `note`. Deliberate."""

    id: str
    text: str


class QuizQuestionOut(ApiModel):
    """Note the absence of `explanation`. It arrives with a graded attempt."""

    id: str
    type: Literal["single_choice", "multi_choice", "ordering", "fill_command"]
    level: str
    stem: str
    options: list[QuizOptionOut]


class QuizOut(ApiModel):
    topic_slug: str
    pass_score: int
    question_count: int
    questions: list[QuizQuestionOut]


# -------------------------------------------------------------- other items


class ExerciseOut(ApiModel):
    id: str
    title: str
    level: str
    kind: str
    prompt: str


class TroubleshootingOut(ApiModel):
    """No `root_cause`, no `method`, no `resolution`, no `hints`.

    Those are gated behind a submitted hypothesis (Phase 2). Serving them here
    would defeat the entire pedagogical point of the exercise.
    """

    id: str
    title: str
    level: str
    reveal_policy: str
    situation: str
    symptoms: list[str]
    artifacts: list[dict]
    diagnostic_questions: list[str]


class InterviewQuestionOut(ApiModel):
    """No `model_answer`, no `signal` — revealed on request, per question."""

    id: str
    level: str
    question: str
    follow_ups: list[str]


class AssessmentPartOut(ApiModel):
    """No `rubric`, no `model_answer`, no `common_failures`."""

    id: str
    title: str
    kind: str
    prompt: str


class LabDetailOut(ApiModel):
    slug: str
    title: str
    type: str
    tier: int
    image: str
    duration_minutes: int
    objectives: list[str]
    intro: str
    steps: list[dict]


class RoadmapTopicOut(ApiModel):
    slug: str
    title: str
    levels: list[str]
    estimated_minutes: int
    status: str


class RoadmapModuleOut(ApiModel):
    slug: str
    title: str
    topics: list[RoadmapTopicOut]


class RoadmapCourseOut(ApiModel):
    slug: str
    code: str
    title: str
    summary: str
    track: str
    levels: list[str]
    estimated_hours: int
    modules: list[RoadmapModuleOut]
    topic_count: int
    published_topic_count: int


class RoadmapOut(ApiModel):
    path_slug: str
    title: str
    summary: str
    courses: list[RoadmapCourseOut]
    total_topics: int
    published_topics: int
    content_version: str | None = None
    ingested_at: datetime | None = None


# ------------------------------------------------------------------- outline


class OutlineStepOut(ApiModel):
    """One screen in the course player.

    A topic is delivered as an ordered sequence of these rather than one long
    page: lesson sections, then practice, then assessment. `entity_type` and
    `entity_id` are what progress is recorded against.
    """

    slug: str
    kind: str
    title: str
    subtitle: str | None = None
    entity_type: str
    entity_id: str
    estimated_minutes: int | None = None
    level: str | None = None


class TopicOutlineOut(ApiModel):
    topic_slug: str
    topic_title: str
    course: TopicNavOut
    module: TopicNavOut
    estimated_minutes: int
    steps: list[OutlineStepOut]
