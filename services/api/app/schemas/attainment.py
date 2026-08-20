"""Achievement, competence and certificate response models.

The verification model is the one to read carefully: it carries a display name
and a course, and nothing else. A public endpoint that also returned an email or
a user id would turn a credential into a way of looking someone up.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AchievementOut(BaseModel):
    code: str
    scope: str = ""
    title: str
    detail: str = ""
    earned_at: datetime | None = None


class ObjectiveScoreOut(BaseModel):
    code: str
    statement: str
    score: int = Field(ge=0, le=100)
    proficient: bool
    # Which kinds of evidence contributed, and how much. Shown to the learner so
    # "why am I not proficient yet" has a concrete answer: usually "you have
    # only done the quiz".
    sources: dict[str, int] = Field(default_factory=dict)


class TopicCompetenceOut(BaseModel):
    topic_slug: str
    topic_title: str
    # The weakest objective, not the average. See services/competence.py.
    score: int = Field(ge=0, le=100)
    mastered: bool
    proficient_at: int
    objectives: list[ObjectiveScoreOut]


class CourseCompetenceOut(BaseModel):
    course_slug: str
    course_code: str
    course_title: str
    score: int = Field(ge=0, le=100)
    mastered: bool
    topics_total: int
    topics_mastered: int
    topics: list[TopicCompetenceOut]


class CertificateOut(BaseModel):
    code: str
    course_code: str
    course_title: str
    holder_name: str
    topics_completed: int
    weakest_objective_score: int
    issued_at: datetime


class CertificateVerificationOut(BaseModel):
    code: str
    valid: bool
    holder_name: str
    course_code: str
    course_title: str
    topics_completed: int
    weakest_objective_score: int
    issued_at: datetime
