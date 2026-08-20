"""Ingest integration tests — real PostgreSQL.

The most important test in the repository is
`test_progress_survives_content_reorganisation`. It guards against the failure
mode that would quietly destroy this platform: a learner completes a topic, we
later rename a directory or reorder a module, and their progress silently stops
resolving. That bug is invisible for months and unfixable afterwards.

Skipped automatically when no database is reachable, so the fast unit suite
still runs anywhere.
"""

from __future__ import annotations

import os
import textwrap
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.content.ingest import ingest
from app.content.loader import ContentTree, load_content
from app.models.curriculum import (
    Course,
    Lab,
    Lesson,
    Module,
    Objective,
    Quiz,
    QuizOption,
    QuizQuestion,
    Topic,
    TopicItem,
)
from app.models.search import ContentSearch


def load_valid(root: Path) -> ContentTree:
    """Load content, failing the test if it does not validate.

    Without this, a malformed fixture ingests zero rows and the assertions fail
    somewhere far away with no indication of why.
    """
    tree = load_content(root)
    problems = "\n".join(str(error) for error in tree.errors)
    assert tree.ok, f"fixture content is invalid:\n{problems}"
    return tree


pytestmark = pytest.mark.skipif(
    os.environ.get("POSTGRES_HOST") in (None, "localhost"),
    reason="no database available",
)


TEST_DATABASE = "groundwork_ingest_test"


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """A session against a dedicated test database.

    These tests truncate the curriculum, so they must never touch the
    development database — running the suite should not wipe the content you
    just ingested. The database is created on first use and reused after that.
    """
    from app.core.config import get_settings
    from app.db.base import Base

    settings = get_settings()
    admin_url = settings.database_url
    test_url = admin_url.rsplit("/", 1)[0] + f"/{TEST_DATABASE}"

    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as connection:
        exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DATABASE}
        )
        if not exists:
            await connection.execute(text(f'CREATE DATABASE "{TEST_DATABASE}"'))
    await admin_engine.dispose()

    # pg_trgm must exist before create_all, because the search index declares a
    # gin_trgm_ops index. It also has to be committed on its own: created inside
    # the same transaction as create_all, a failure rolls the extension back too
    # and every later run fails identically.
    prep_engine = create_async_engine(test_url, isolation_level="AUTOCOMMIT")
    async with prep_engine.connect() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    await prep_engine.dispose()

    engine = create_async_engine(test_url)
    async with engine.begin() as connection:
        # Schema comes from the models rather than from Alembic: these tests are
        # about ingestion behaviour, and migration correctness is tested
        # separately by running them forward and backward in CI.
        await connection.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with maker() as s:
        await s.execute(text("TRUNCATE learning_paths, courses, content_versions CASCADE"))
        await s.commit()
        yield s
    await engine.dispose()


def write_tree(
    root: Path,
    *,
    course_dir: str = "01-course",
    topic_dir: str = "01-topic",
    topic_title: str = "Original Title",
    topic_order: int = 1,
) -> None:
    """Writes a minimal, valid content tree.

    Every argument is a thing that *may legitimately change* over a curriculum's
    life. None of them may change a database key.
    """
    path = root / "courses" / course_dir / "modules" / "01-module" / "topics" / topic_dir
    (path / "lessons").mkdir(parents=True)

    (root / "paths").mkdir(exist_ok=True)
    (root / "paths" / "main.yaml").write_text(
        textwrap.dedent("""
            id: path.main
            slug: main-path
            title: Main Path
            summary: A learning path summary long enough to satisfy validation.
            courses:
              - course: course.demo
                order: 1
        """).strip(),
        encoding="utf-8",
    )
    (root / "courses" / course_dir / "course.yaml").write_text(
        textwrap.dedent("""
            id: course.demo
            slug: demo-course
            code: A01
            title: Demo Course
            summary: A course summary long enough to satisfy the validation rules.
            track: Foundations
            levels: [L1]
            estimated_hours: 1
            order: 1
        """).strip(),
        encoding="utf-8",
    )
    (root / "courses" / course_dir / "modules" / "01-module" / "module.yaml").write_text(
        textwrap.dedent("""
            id: module.demo
            slug: demo-module
            title: Demo Module
            summary: A module summary long enough to satisfy the validation rules.
            order: 1
        """).strip(),
        encoding="utf-8",
    )
    (path / "topic.yaml").write_text(
        textwrap.dedent(f"""
            id: topic.demo
            slug: demo-topic
            title: {topic_title}
            summary: A topic summary long enough to satisfy the validation rules.
            order: {topic_order}
            levels: [L1]
            estimated_minutes: 30
            objectives:
              - id: OBJ-1.1
                level: L1
                verb: explain
                statement: Explain the thing that this topic is actually about.
                assessed_by: [quiz.q1]
        """).strip(),
        encoding="utf-8",
    )
    (path / "lessons" / "01-overview.md").write_text(
        "---\ntopic: topic.demo\nsection: overview\ntitle: Overview\norder: 1\n---\n\nBody.\n",
        encoding="utf-8",
    )
    (path / "quiz.yaml").write_text(
        textwrap.dedent("""
            id: quiz.demo
            topic: topic.demo
            pass_score: 70
            questions:
              - id: q1
                type: single_choice
                level: L1
                objectives: [OBJ-1.1]
                stem: Which statement is true about this demo question?
                options:
                  - {id: a, text: The right one, correct: true}
                  - {id: b, text: The wrong one, note: A distractor with a note.}
                  - {id: c, text: Another wrong one}
                explanation: The first option is correct for demonstration purposes.
              - id: q2
                type: single_choice
                level: L1
                objectives: [OBJ-1.1]
                stem: Which statement is true about the second demo question?
                options:
                  - {id: a, text: The right one, correct: true}
                  - {id: b, text: The wrong one, note: A distractor with a note.}
                explanation: The first option is correct for demonstration purposes.
              - id: q3
                type: single_choice
                level: L1
                objectives: [OBJ-1.1]
                stem: Which statement is true about the third demo question?
                options:
                  - {id: a, text: The right one, correct: true}
                  - {id: b, text: The wrong one, note: A distractor with a note.}
                explanation: The first option is correct for demonstration purposes.
        """).strip(),
        encoding="utf-8",
    )


async def test_ingest_creates_the_expected_rows(session: AsyncSession, tmp_path: Path) -> None:
    write_tree(tmp_path)
    result = await ingest(session, load_valid(tmp_path), "abc123")

    assert result.topics == 1
    assert result.questions == 3
    assert await session.scalar(select(func.count()).select_from(Topic)) == 1
    assert await session.scalar(select(func.count()).select_from(QuizOption)) == 7


async def test_ingest_is_idempotent(session: AsyncSession, tmp_path: Path) -> None:
    write_tree(tmp_path)
    tree = load_valid(tmp_path)

    await ingest(session, tree, "abc123")
    first = {
        model.__name__: await session.scalar(select(func.count()).select_from(model))
        for model in (Course, Module, Topic, Lesson, Objective, Quiz, QuizQuestion, QuizOption)
    }

    await ingest(session, load_valid(tmp_path), "abc123")
    second = {
        model.__name__: await session.scalar(select(func.count()).select_from(model))
        for model in (Course, Module, Topic, Lesson, Objective, Quiz, QuizQuestion, QuizOption)
    }

    assert first == second


async def test_progress_survives_content_reorganisation(
    session: AsyncSession, tmp_path: Path
) -> None:
    """THE regression test.

    Simulates a learner completing a topic, then the curriculum being
    reorganised in every way that is legitimate — directory renamed, topic
    retitled, position changed — and asserts every key a progress row could
    point at is unchanged.
    """
    write_tree(tmp_path)
    await ingest(session, load_valid(tmp_path), "before")

    topic_key = await session.scalar(select(Topic.id).where(Topic.content_id == "topic.demo"))
    lesson_key = await session.scalar(select(Lesson.id))
    question_key = await session.scalar(select(QuizQuestion.id))
    objective_key = await session.scalar(select(Objective.id))
    assert topic_key and lesson_key and question_key and objective_key

    # A learner's progress row would reference exactly these.
    original = (topic_key, lesson_key, question_key, objective_key)

    # Now reorganise: rename the course directory, rename the topic directory,
    # retitle the topic, and move it to a different position.
    reorganised = tmp_path / "v2"
    reorganised.mkdir()
    write_tree(
        reorganised,
        course_dir="07-renamed-course",
        topic_dir="03-renamed-topic",
        topic_title="A Completely Different Title",
        topic_order=4,
    )
    await ingest(session, load_valid(reorganised), "after")

    after = (
        await session.scalar(select(Topic.id).where(Topic.content_id == "topic.demo")),
        await session.scalar(select(Lesson.id)),
        await session.scalar(select(QuizQuestion.id)),
        await session.scalar(select(Objective.id)),
    )

    assert after == original, (
        "Content reorganisation changed a database key. Every learner's progress "
        "for this topic would now be orphaned."
    )

    # And the content itself did update.
    title = await session.scalar(select(Topic.title).where(Topic.content_id == "topic.demo"))
    assert title == "A Completely Different Title"


async def test_removed_content_is_pruned(session: AsyncSession, tmp_path: Path) -> None:
    write_tree(tmp_path)
    await ingest(session, load_valid(tmp_path), "before")
    assert await session.scalar(select(func.count()).select_from(Topic)) == 1

    empty = tmp_path / "empty"
    (empty / "courses").mkdir(parents=True)
    (empty / "paths").mkdir()
    await ingest(session, load_valid(empty), "after")

    assert await session.scalar(select(func.count()).select_from(Topic)) == 0
    assert await session.scalar(select(func.count()).select_from(Course)) == 0


async def test_answer_keys_are_stored_but_separated(session: AsyncSession, tmp_path: Path) -> None:
    """The key must be in the database — and never in the public payload."""
    write_tree(tmp_path)
    await ingest(session, load_valid(tmp_path), "abc")

    correct = await session.scalar(
        select(func.count()).select_from(QuizOption).where(QuizOption.is_correct)
    )
    assert correct == 3

    for item in await session.scalars(select(TopicItem)):
        payload = str(item.payload).lower()
        for banned in ("model_answer", "root_cause", "rubric", '"answer"'):
            assert banned not in payload, f"{item.kind}/{item.content_id} leaks {banned}"


async def test_ingest_refuses_nothing_and_reports_counts(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Counts in the result are what the CLI and the roadmap surface report."""
    write_tree(tmp_path)
    result = await ingest(session, load_valid(tmp_path), "abc")
    assert result.version_id is not None
    assert "1 topics" in result.summary()


async def test_labs_round_trip_their_spec(session: AsyncSession, tmp_path: Path) -> None:
    write_tree(tmp_path)
    path = tmp_path / "courses/01-course/modules/01-module/topics/01-topic"
    (path / "labs").mkdir()
    (path / "labs" / "01-demo.yaml").write_text(
        textwrap.dedent("""
            id: lab.demo
            topic: topic.demo
            title: A demonstration lab
            type: guided
            tier: 2
            image: groundwork/lab-foundations:1
            duration_minutes: 10
            objectives: [OBJ-1.1]
            intro: An introduction long enough to satisfy the validation rules.
            steps:
              - id: s1
                instruction: Do the thing that this step asks you to do.
                verify:
                  - type: file_exists
                    path: /tmp/answer
                    describe: The answer file exists
            solution: An explanation of the solution, long enough to validate.
        """).strip(),
        encoding="utf-8",
    )

    await ingest(session, load_valid(tmp_path), "abc")
    lab = await session.scalar(select(Lab))
    assert lab is not None
    assert lab.spec["steps"][0]["verify"][0]["type"] == "file_exists"
    assert lab.tier == 2


# --------------------------------------------------------------------- search


PRIVATE_ROOT_CAUSE = "the widget cache was seeded from a stale replica overnight"
PRIVATE_LAB_SOLUTION = "the trick is that the marker file was never created at all"


def write_gated_content(root: Path) -> None:
    """Adds content whose most interesting text is deliberately gated.

    A troubleshooting root cause is only served after the learner submits a
    hypothesis, and a lab's solution text sits inside its spec. Both phrases
    below exist nowhere else, so finding either one through search is
    unambiguous evidence of a leak.
    """
    path = root / "courses/01-course/modules/01-module/topics/01-topic"
    (path / "troubleshooting").mkdir(exist_ok=True)
    (path / "troubleshooting" / "01-case.yaml").write_text(
        textwrap.dedent(f"""
            id: troubleshooting.case
            topic: topic.demo
            title: The dashboard shows yesterday's numbers
            level: L3
            objectives: [OBJ-1.1]
            reveal_policy: progressive
            situation: >-
              Every morning the dashboard shows figures that are one day out of
              date, and by midday it corrects itself without intervention.
            symptoms:
              - "Numbers are stale until roughly midday"
              - "No errors anywhere in the logs"
            artifacts:
              - type: log
                label: Loader output
                content: "loader finished in 42s, 0 errors"
            diagnostic_questions:
              - "What runs overnight that could produce yesterday's data?"
            hints:
              - "Look at what the overnight job reads from."
            root_cause: >-
              {PRIVATE_ROOT_CAUSE}, so every overnight load read data that was
              already a day behind before the job even started.
            method: >-
              Compare the timestamps on the source rows against the job start
              time, which separates a slow job from a job reading stale input.
            resolution: >-
              Point the loader at the primary, or wait for replica lag to clear
              before starting it.
        """).strip(),
        encoding="utf-8",
    )


async def test_search_index_is_populated_by_ingest(session: AsyncSession, tmp_path: Path) -> None:
    write_tree(tmp_path)
    result = await ingest(session, load_valid(tmp_path), "abc")

    rows = await session.scalar(select(func.count()).select_from(ContentSearch))
    assert rows and rows > 0
    assert result.search_rows == rows

    kinds = set(await session.scalars(select(ContentSearch.entity_type)))
    assert {"topic", "lesson"} <= kinds


async def test_search_index_never_contains_gated_text(
    session: AsyncSession, tmp_path: Path
) -> None:
    """The index is built from public columns, and this is what proves it.

    Search is the obvious way to accidentally route around every gate in the
    product: the troubleshooting reveal, the quiz answer key, a lab solution.
    One careless `payload | solution` in the index builder would do it silently,
    because nothing else in the system would fail.
    """
    write_tree(tmp_path)
    write_gated_content(tmp_path)
    await ingest(session, load_valid(tmp_path), "abc")

    # The gated text really is in the database — otherwise this test passes for
    # the wrong reason.
    scenario = await session.scalar(select(TopicItem).where(TopicItem.kind == "troubleshooting"))
    assert scenario is not None
    assert PRIVATE_ROOT_CAUSE in scenario.solution["root_cause"]

    indexed = " ".join(
        f"{row.title} {row.subtitle or ''} {row.body}"
        for row in await session.scalars(select(ContentSearch))
    ).lower()

    assert PRIVATE_ROOT_CAUSE not in indexed
    assert "stale replica" not in indexed
    # The method and resolution are gated with the root cause and must not leak
    # either — they give the answer away just as completely.
    assert "replica lag" not in indexed

    # ...while the public half of the same scenario is findable, or the gate has
    # simply removed the content from search altogether.
    assert "one day out of" in indexed
    assert "dashboard shows" in indexed


async def test_search_index_excludes_quiz_answers(session: AsyncSession, tmp_path: Path) -> None:
    write_tree(tmp_path)
    await ingest(session, load_valid(tmp_path), "abc")

    correct_texts = [
        text_value.lower()
        for text_value in await session.scalars(
            select(QuizOption.text).where(QuizOption.is_correct)
        )
    ]
    assert correct_texts, "fixture has no correct options to check against"

    indexed = " ".join(
        f"{row.title} {row.body}" for row in await session.scalars(select(ContentSearch))
    ).lower()

    for answer in correct_texts:
        assert answer not in indexed, f"search index contains a quiz answer: {answer!r}"


async def test_search_index_is_rebuilt_not_appended(session: AsyncSession, tmp_path: Path) -> None:
    """Re-ingesting must not double the corpus or leave rows for deleted content."""
    write_tree(tmp_path)
    await ingest(session, load_valid(tmp_path), "abc")
    first = await session.scalar(select(func.count()).select_from(ContentSearch))

    await ingest(session, load_valid(tmp_path), "def")
    second = await session.scalar(select(func.count()).select_from(ContentSearch))

    assert first == second
