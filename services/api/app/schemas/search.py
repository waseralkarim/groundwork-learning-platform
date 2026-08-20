"""Search response models.

There is no field here for an answer, a root cause, a model answer or a lab
solution, and that absence is the enforcement. Adding one would require adding a
column to the index that the builder never populates.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SearchHitOut(BaseModel):
    entity_type: str = Field(description="topic, lesson, lab, troubleshooting, glossary, …")
    title: str
    subtitle: str | None = None
    url: str = Field(description="Where clicking this result should go")
    topic_slug: str | None = None
    topic_title: str | None = None
    # Contains <mark> tags around the matched terms. Rendered as markup by the
    # web app, which is safe because the index holds curriculum prose from git,
    # never anything a user submitted.
    snippet: str | None = None


class SearchResultsOut(BaseModel):
    query: str
    total: int
    hits: list[SearchHitOut]
