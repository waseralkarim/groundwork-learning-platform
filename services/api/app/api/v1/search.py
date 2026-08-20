"""Full-text search across the curriculum.

Postgres FTS, not a separate search service. The corpus is a few megabytes of
prose that changes only when someone commits to `content/`, and a second
datastore would be a second thing to keep in sync, back up and explain. When
this stops being enough — typo tolerance beyond trigrams, faceting, cross-type
ranking that actually needs tuning — Meilisearch goes behind the `search`
Compose profile and this module becomes its client.

The response model carries no field for an answer, a root cause or a solution,
and the index it reads has no column for one either. That is deliberate: a
search box that returns gated content is a gate that does not exist.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import cast, func, literal, or_, select
from sqlalchemy.dialects.postgresql import REGCONFIG
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import record_search
from app.db.session import get_session
from app.models.search import ContentSearch
from app.schemas.search import SearchHitOut, SearchResultsOut

router = APIRouter(tags=["search"])

# Entity types a learner can filter by. Closed set, so a crafted `type` cannot
# probe for tables that are not meant to be searchable.
FILTERABLE = frozenset(
    {
        "topic",
        "lesson",
        "lab",
        "troubleshooting",
        "glossary",
        "exercise",
        "interview",
        "assessment",
        "quiz",
    }
)


@router.get("/search", response_model=SearchResultsOut)
async def search(
    q: str = Query(min_length=2, max_length=120, description="What to look for"),
    entity_type: str | None = Query(
        default=None, alias="type", description="Restrict to one entity type"
    ),
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> SearchResultsOut:
    # websearch_to_tsquery accepts what people actually type — quoted phrases,
    # OR, leading minus — and never raises on malformed input. plainto_ and
    # to_tsquery both do, which turns a stray quote into a 500.
    # The text-search config must be a regconfig, not a string: passing a bare
    # literal picks the varchar overload, which does not exist.
    english = cast(literal("english"), REGCONFIG)
    tsquery = func.websearch_to_tsquery(english, q)

    rank = func.ts_rank_cd(ContentSearch.tsv, tsquery)
    # Trigram similarity catches misspellings that FTS cannot: a typo is not a
    # lexeme, so "capabilties" matches nothing until you compare the strings.
    similarity = func.similarity(ContentSearch.title, q)

    headline = func.ts_headline(
        english,
        ContentSearch.body,
        tsquery,
        literal("StartSel=<mark>,StopSel=</mark>,MaxWords=32,MinWords=12,MaxFragments=1"),
    )

    statement = (
        select(
            ContentSearch.entity_type,
            ContentSearch.title,
            ContentSearch.subtitle,
            ContentSearch.url,
            ContentSearch.topic_slug,
            ContentSearch.topic_title,
            headline.label("snippet"),
            rank.label("rank"),
        )
        .where(or_(ContentSearch.tsv.op("@@")(tsquery), similarity > 0.3))
        .order_by(
            (rank + similarity).desc(),
            ContentSearch.weight.asc(),
            ContentSearch.title.asc(),
        )
        .limit(limit)
    )

    if entity_type and entity_type in FILTERABLE:
        statement = statement.where(ContentSearch.entity_type == entity_type)

    rows = (await session.execute(statement)).mappings().all()
    record_search(found=bool(rows))

    return SearchResultsOut(
        query=q,
        total=len(rows),
        hits=[
            SearchHitOut(
                entity_type=row["entity_type"],
                title=row["title"],
                subtitle=row["subtitle"],
                url=row["url"],
                topic_slug=row["topic_slug"],
                topic_title=row["topic_title"],
                # Titles with no body — quiz stems — get no snippet rather than
                # an empty highlighted string.
                snippet=row["snippet"] or None,
            )
            for row in rows
        ],
    )


@router.get("/search/suggest", response_model=list[str])
async def suggest(
    q: str = Query(min_length=2, max_length=80),
    limit: int = Query(default=8, ge=1, le=20),
    session: AsyncSession = Depends(get_session),
) -> list[str]:
    """Title completions for a search box, fuzzy enough to survive a typo."""
    similarity = func.similarity(ContentSearch.title, q)
    statement = (
        select(ContentSearch.title)
        .where(or_(ContentSearch.title.ilike(f"%{q}%"), similarity > 0.25))
        .order_by(similarity.desc(), ContentSearch.weight.asc())
        .limit(limit)
    )
    return list((await session.execute(statement)).scalars().all())


__all__ = ["router"]
