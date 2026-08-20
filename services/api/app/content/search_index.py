"""Rebuild the search index from what has just been ingested.

Built from the database rather than from the content tree on purpose. The DB
rows already carry the public/private split the API enforces — `payload` versus
`solution`, quiz options separate from their `is_correct` flag — so indexing
from them means the index inherits that split instead of re-deriving it and
getting it subtly wrong.

Nothing in this module reads `TopicItem.solution`, `QuizOption.is_correct`, a
lab's steps or its solution text. Searching must never be a way around a gate
that the rest of the API takes seriously: a learner who has not submitted a
hypothesis cannot see a scenario's root cause, and typing it into a search box
must not be the exception. There is a test that asserts exactly this.
"""

from __future__ import annotations

import re

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.curriculum import (
    GlossaryTerm,
    Quiz,
    QuizQuestion,
    Topic,
    TopicItem,
    content_uuid,
)
from app.models.search import ContentSearch

# Lower sorts first among equally-ranked hits: a topic beats a lesson inside it,
# and a quiz question is the least useful thing to land on.
WEIGHTS = {
    "topic": 10,
    "lesson": 20,
    "lab": 30,
    "troubleshooting": 40,
    "glossary": 50,
    "exercise": 60,
    "interview": 70,
    "assessment": 80,
    "quiz": 90,
}

_DIRECTIVE = re.compile(r"^:::[a-z-]*(?:\{[^}]*\})?\s*$", re.MULTILINE)
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
# Diagram source is pure syntax — node ids, arrow operators, `<br/>` — and is
# never something a reader is looking for. It is removed whole, block and all,
# rather than having its fence markers stripped and its contents indexed.
_MERMAID_BLOCK = re.compile(r"^```mermaid\n.*?^```\s*$", re.MULTILINE | re.DOTALL)
_FENCE = re.compile(r"^```.*$", re.MULTILINE)
_MD_NOISE = re.compile(r"[*_`#>|]")
# Angle brackets are stripped so that `ts_headline` can only ever emit the
# <mark> tags it adds itself. The snippet is rendered as HTML, and a lesson that
# happens to contain a `<br/>` would otherwise close the paragraph around it and
# corrupt the page structure — invalid markup from entirely trusted content.
_ANGLE = re.compile(r"[<>]")


def plain_text(markdown: str) -> str:
    """Strip the markup so the index holds prose, not syntax.

    Without this, `:::warning{scope=production}` contributes the lexemes
    "warning", "scope" and "production" to every lesson that has one, and a
    search for "production" returns the whole curriculum.
    """
    text = _FRONTMATTER.sub("", markdown)
    text = _MERMAID_BLOCK.sub("", text)
    text = _DIRECTIVE.sub("", text)
    text = _FENCE.sub("", text)
    text = _MD_NOISE.sub("", text)
    text = _ANGLE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _row(
    key: str,
    entity_type: str,
    title: str,
    body: str,
    url: str,
    *,
    subtitle: str | None = None,
    topic: Topic | None = None,
) -> ContentSearch:
    return ContentSearch(
        id=content_uuid(f"search#{key}"),
        entity_type=entity_type,
        topic_id=topic.id if topic else None,
        topic_slug=topic.slug if topic else None,
        topic_title=topic.title if topic else None,
        title=title[:300],
        subtitle=subtitle[:300] if subtitle else None,
        body=body[:20000],
        url=url[:300],
        weight=WEIGHTS.get(entity_type, 100),
    )


async def rebuild(session: AsyncSession) -> int:
    """Replace the whole index. Returns the number of rows written.

    A full rebuild rather than an incremental update because ingest is already
    a whole-corpus operation and the corpus is small. An incremental index is a
    second source of truth about what content exists, and this project has had
    quite enough of those.
    """
    await session.execute(delete(ContentSearch))

    topics = (
        (
            await session.execute(
                select(Topic).options(
                    selectinload(Topic.lessons),
                    selectinload(Topic.labs),
                    selectinload(Topic.items),
                )
            )
        )
        .scalars()
        .all()
    )

    rows: list[ContentSearch] = []

    for topic in topics:
        terminology = " ".join(
            f"{term.get('term', '')} {term.get('definition', '')}"
            for term in (topic.terminology or [])
        )
        rows.append(
            _row(
                f"topic#{topic.id}",
                "topic",
                topic.title,
                f"{topic.summary} {terminology}",
                f"/topics/{topic.slug}",
                subtitle="Topic",
                topic=topic,
            )
        )

        for lesson in topic.lessons:
            rows.append(
                _row(
                    f"lesson#{lesson.id}",
                    "lesson",
                    lesson.title,
                    plain_text(lesson.body_md),
                    f"/learn/{topic.slug}/read-{lesson.section}",
                    subtitle=f"Lesson · {topic.title}",
                    topic=topic,
                )
            )

        for lab in topic.labs:
            # Intro only. Steps carry their verification checks and the spec
            # carries the solution; neither belongs in a search result.
            rows.append(
                _row(
                    f"lab#{lab.id}",
                    "lab",
                    lab.title,
                    str(lab.spec.get("intro", "")),
                    f"/learn/{topic.slug}/lab-{lab.slug}",
                    subtitle=f"{lab.type.title()} lab · {topic.title}",
                    topic=topic,
                )
            )

        for item in topic.items:
            body, url, subtitle = _item_projection(item, topic)
            if body is None:
                continue
            rows.append(
                _row(
                    f"item#{item.id}",
                    item.kind,
                    item.title,
                    body,
                    url,
                    subtitle=subtitle,
                    topic=topic,
                )
            )

    # Quiz question stems, so "what does EPERM mean" can find the question that
    # asks it. Deliberately not the options and not the explanation — both give
    # the answer away, and a search box is not an exam gate.
    questions = (
        (
            await session.execute(
                select(QuizQuestion, Topic)
                .join(Quiz, QuizQuestion.quiz_id == Quiz.id)
                .join(Topic, Quiz.topic_id == Topic.id)
            )
        )
        .tuples()
        .all()
    )
    for question, topic in questions:
        rows.append(
            _row(
                f"quiz#{question.id}",
                "quiz",
                question.stem[:200],
                "",
                f"/learn/{topic.slug}/quiz",
                subtitle=f"Quiz question · {topic.title}",
                topic=topic,
            )
        )

    terms = (await session.execute(select(GlossaryTerm))).scalars().all()
    topics_by_id = {topic.id: topic for topic in topics}
    for term in terms:
        topic = topics_by_id.get(term.defined_in_topic_id) if term.defined_in_topic_id else None
        rows.append(
            _row(
                f"glossary#{term.id}",
                "glossary",
                term.term,
                term.definition,
                f"/topics/{topic.slug}" if topic else "/glossary",
                subtitle=f"Term · defined in {topic.title}" if topic else "Term",
                topic=topic,
            )
        )

    session.add_all(rows)
    await session.flush()
    return len(rows)


def _item_projection(item: TopicItem, topic: Topic) -> tuple[str | None, str, str | None]:
    """Public text, URL and subtitle for one topic item.

    Reads `item.payload` and never `item.solution`. Exercises keep their answer
    and explanation in solution; troubleshooting keeps root cause, method,
    resolution and hints there; interview questions keep the model answer and
    the signal. All of that is invisible from here by construction.
    """
    payload = item.payload or {}
    base = f"/learn/{topic.slug}"

    if item.kind == "exercise":
        return payload.get("prompt", ""), f"{base}/exercise", f"Exercise · {topic.title}"

    if item.kind == "troubleshooting":
        symptoms = " ".join(payload.get("symptoms", []) or [])
        questions = " ".join(payload.get("diagnostic_questions", []) or [])
        slug = item.content_id.rsplit(".", 1)[-1]
        return (
            f"{payload.get('situation', '')} {symptoms} {questions}",
            f"{base}/diagnose-{slug}",
            f"Troubleshooting · {topic.title}",
        )

    if item.kind == "interview":
        return (
            payload.get("question", ""),
            f"{base}/interview",
            f"Interview question · {topic.title}",
        )

    if item.kind == "assessment":
        prompts = " ".join(part.get("prompt", "") for part in payload.get("parts", []) or [])
        return prompts, f"{base}/assessment", f"Assessment · {topic.title}"

    return None, "", None


__all__ = ["WEIGHTS", "plain_text", "rebuild"]
