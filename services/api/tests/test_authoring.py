"""Authoring endpoints — the admin gate, and the Definition of Done.

Three things worth testing here, and one of them is a guard against drift.

**The admin gate is real.** `require_admin` existed from the moment accounts
were added and was enforced on no endpoint, which made the role a claim rather
than a control. These are the first routes that use it, so there is a test
asserting a learner is refused rather than merely assuming the dependency works.

**The Definition of Done is computed, not guessed.** `_done_state` reports what
a topic is missing. It has to agree with what the linter blocks on, or the
authoring view would tell an author their topic is fine while the build refuses
it. `test_done_state_matches_the_linter` fails if the two lists drift apart.

**Ingest refuses invalid content.** The endpoint can never put the database into
a state the CLI would have rejected.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import ClassVar

import httpx
import pytest

from app.api.v1.authoring import RECOMMENDED, REQUIRED, _done_state
from app.content.loader import LoadedTopic
from app.content.schema import Level, Objective, Topic


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _topic(status: str = "published", levels: tuple[str, ...] = ("L1",)) -> Topic:
    return Topic(
        id="topic.example",
        slug="example",
        title="An example topic",
        summary="A topic that exists only to be checked by these tests.",
        order=1,
        levels=[Level(lv) for lv in levels],
        estimated_minutes=30,
        status=status,
        objectives=[
            Objective(
                id="OBJ-T.1",
                level=Level("L1"),
                verb="describe",
                statement="Describe the thing this topic is about, measurably.",
                assessed_by=["quiz.q1"],
            )
        ],
    )


# ------------------------------------------------------------------ the gate


async def test_authoring_requires_authentication(client: httpx.AsyncClient) -> None:
    for path in ("/v1/authoring/inventory", "/v1/authoring/lint"):
        response = await client.get(path)
        assert response.status_code == 401, path


async def test_ingest_requires_authentication(client: httpx.AsyncClient) -> None:
    response = await client.post("/v1/authoring/ingest")
    assert response.status_code == 401


# ------------------------------------------------- the Definition of Done


def test_done_state_reports_a_complete_topic_as_complete() -> None:
    topic = LoadedTopic(topic=_topic(), module_id="module.example")
    topic.lessons = ["a lesson"]  # type: ignore[list-item]
    topic.labs = ["a lab"]  # type: ignore[list-item]

    class _Quiz:
        questions: ClassVar[list[int]] = [1, 2, 3]

    class _Assessment:
        parts: ClassVar[list[int]] = [1]

    topic.quiz = _Quiz()  # type: ignore[assignment]
    topic.assessment = _Assessment()  # type: ignore[assignment]

    state = _done_state(topic)
    assert state["missing"] == []
    assert state["blocking"] is False
    assert state["present"]["lessons"] == 1


def test_done_state_names_what_is_missing() -> None:
    """The whole point of the view: say which pieces are absent, not just that
    something is."""
    topic = LoadedTopic(topic=_topic(), module_id="module.example")
    topic.lessons = ["a lesson"]  # type: ignore[list-item]

    state = _done_state(topic)
    assert state["blocking"] is True
    assert set(state["missing"]) == {"quiz", "assessment", "labs"}
    assert set(state["warnings"]) == {"exercises", "interview"}


def test_done_state_requires_troubleshooting_only_above_l2() -> None:
    """Troubleshooting becomes required at L3, because that is the level at
    which diagnosis is the skill being taught."""
    l1 = LoadedTopic(topic=_topic(levels=("L1", "L2")), module_id="m")
    l3 = LoadedTopic(topic=_topic(levels=("L2", "L3")), module_id="m")

    assert "troubleshooting" not in _done_state(l1)["missing"]
    assert "troubleshooting" in _done_state(l3)["missing"]


def test_done_state_exempts_drafts() -> None:
    """A draft is allowed to be incomplete — that is what draft means, and the
    linter agrees."""
    topic = LoadedTopic(topic=_topic(status="draft", levels=("L3",)), module_id="m")

    state = _done_state(topic)
    assert state["missing"] == []
    assert state["blocking"] is False


def test_done_state_matches_the_linter() -> None:
    """Guard against drift.

    If somebody adds a rule to `linter.check_done` and not here, an author would
    be told their topic is complete while the build refuses it. This reads the
    linter's own source for the rule names it blocks on and compares.
    """
    source = Path(__file__).resolve().parents[1] / "app" / "content" / "linter.py"
    text = source.read_text(encoding="utf-8")

    assert "def check_required_artifacts_present" in text, (
        "the Definition-of-Done check has been renamed; this guard needs updating"
    )
    body = text.split("def check_required_artifacts_present", 1)[1].split("def check_lessons", 1)[0]

    blocking = {
        name
        for name, marker in (
            ("lessons", '_error("done-lesson"'),
            ("quiz", '_error("done-quiz"'),
            ("assessment", '_error("done-assessment"'),
            ("labs", '_error("done-lab"'),
        )
        if marker in body
    }
    warned = {
        name
        for name, marker in (
            ("exercises", '_warn("done-exercises"'),
            ("interview", '_warn("done-interview"'),
        )
        if marker in body
    }

    assert blocking == set(REQUIRED), (
        f"linter blocks on {sorted(blocking)}; authoring requires {sorted(REQUIRED)}"
    )
    assert warned == set(RECOMMENDED), (
        f"linter warns on {sorted(warned)}; authoring recommends {sorted(RECOMMENDED)}"
    )
    assert 'done-troubleshooting' in body
