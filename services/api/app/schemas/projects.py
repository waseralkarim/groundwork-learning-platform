"""Project and self-review models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RubricCriterionOut(BaseModel):
    id: str
    criterion: str
    excellent: str
    adequate: str
    inadequate: str
    evidence: str
    weight: int = 1


class ProjectSummaryOut(BaseModel):
    slug: str
    title: str
    level: str
    estimated_hours: int
    summary: str
    requires_topics: list[str]
    unlocked: bool


class ProjectDetailOut(ProjectSummaryOut):
    # Empty until the required topics are complete — the gate is applied in the
    # router, not by hiding a field the client could ask for another way.
    brief: str = ""
    constraints: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    rubric: list[RubricCriterionOut] = Field(default_factory=list)
    going_further: list[str] = Field(default_factory=list)
    missing_topics: list[str] = Field(default_factory=list)


class ScoreIn(BaseModel):
    criterion_id: str = Field(min_length=1, max_length=8)
    score: str = Field(description="inadequate | adequate | excellent")
    # The whole point of the exercise. A score with nothing pointed at is an
    # opinion, and the endpoint refuses it.
    evidence: str = Field(
        min_length=10,
        max_length=1000,
        description="What in your own work justifies this score",
    )


class SubmissionIn(BaseModel):
    # Stored and shown back, never fetched by the server. See the router.
    artifact_url: str | None = Field(default=None, max_length=500)
    notes: str = Field(default="", max_length=5000)
    scores: list[ScoreIn] = Field(min_length=1)


class SubmissionOut(BaseModel):
    id: str
    artifact_url: str | None
    notes: str
    scores: list[dict]
    self_score: int
    submitted_at: datetime
