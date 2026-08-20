"""Auth, grading and gating — against a real database.

These are the tests that make a score mean something. The three that matter most:

- `test_grading_ignores_what_the_client_claims` — a forged submission cannot
  award itself a score.
- `test_solution_is_locked_until_a_hypothesis_exists` — the reveal gate is
  enforced in the API, not the UI.
- `test_login_does_not_reveal_whether_an_account_exists` — the login endpoint is
  not an account enumeration oracle.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.content.ingest import ingest
from app.content.loader import load_content
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.models.curriculum import Quiz, QuizQuestion, Topic, TopicItem
from app.models.identity import Hypothesis, QuizAnswer, Session, User, UserProgress
from app.services import auth, learning

pytestmark = pytest.mark.skipif(
    os.environ.get("POSTGRES_HOST") in (None, "localhost"),
    reason="no database available",
)

TEST_DATABASE = "groundwork_auth_test"
REPO_CONTENT = Path("/content")


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    from app.core.config import get_settings
    from app.db.base import Base

    settings = get_settings()
    test_url = settings.database_url.rsplit("/", 1)[0] + f"/{TEST_DATABASE}"

    admin = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DATABASE}
        )
        if not exists:
            await connection.execute(text(f'CREATE DATABASE "{TEST_DATABASE}"'))
    await admin.dispose()

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
        await connection.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with maker() as session:
        await session.execute(
            text(
                "TRUNCATE users, learning_paths, courses, content_versions, login_attempts CASCADE"
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(db: AsyncSession) -> AsyncSession:
    """The real curriculum, so grading is tested against real questions."""
    if not REPO_CONTENT.is_dir():
        pytest.skip("content not mounted")
    tree = load_content(REPO_CONTENT)
    assert tree.ok, "\n".join(str(e) for e in tree.errors)
    await ingest(db, tree, "test")
    return db


async def make_user(db: AsyncSession, email: str = "learner@example.com") -> User:
    user, _ = await auth.register(
        db, email=email, password="a-perfectly-fine-passphrase", display_name="Learner"
    )
    return user


# ------------------------------------------------------------------- hashing


def test_password_hash_is_not_the_password() -> None:
    stored = hash_password("correct-horse-battery-staple")
    assert "correct-horse" not in stored
    assert stored.startswith("$argon2id$")


def test_password_verification_round_trips() -> None:
    stored = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", stored)
    assert not verify_password("Correct-horse-battery-staple", stored)


def test_identical_passwords_hash_differently() -> None:
    """Per-user salts. Two users with the same password must not be detectable."""
    assert hash_password("same-password-here") != hash_password("same-password-here")


def test_session_token_is_not_stored_in_the_clear() -> None:
    token = generate_session_token()
    digest = hash_session_token(token)
    assert token not in digest
    assert len(digest) == 64
    assert hash_session_token(token) == digest


# ---------------------------------------------------------------------- auth


async def test_register_creates_a_usable_session(db: AsyncSession) -> None:
    user, token = await auth.register(
        db, email="a@example.com", password="a-perfectly-fine-passphrase", display_name="A"
    )
    assert await auth.resolve_session(db, token) == user


async def test_the_first_account_is_an_admin_and_later_ones_are_not(db: AsyncSession) -> None:
    first, _ = await auth.register(
        db, email="first@example.com", password="a-perfectly-fine-passphrase", display_name="F"
    )
    second, _ = await auth.register(
        db, email="second@example.com", password="a-perfectly-fine-passphrase", display_name="S"
    )
    assert first.role == "admin"
    assert second.role == "learner"


async def test_registration_rejects_a_short_password(db: AsyncSession) -> None:
    with pytest.raises(auth.WeakPasswordError):
        await auth.register(db, email="a@example.com", password="short", display_name="A")


async def test_registration_rejects_a_duplicate_email(db: AsyncSession) -> None:
    await make_user(db)
    with pytest.raises(auth.EmailAlreadyRegisteredError):
        await make_user(db)


async def test_email_is_normalised(db: AsyncSession) -> None:
    await make_user(db, "Learner@Example.COM")
    user, _ = await auth.login(
        db, email="learner@example.com", password="a-perfectly-fine-passphrase"
    )
    assert user.email == "learner@example.com"


async def test_login_does_not_reveal_whether_an_account_exists(db: AsyncSession) -> None:
    """Both paths must raise the same exception with the same message."""
    await make_user(db)

    with pytest.raises(auth.InvalidCredentialsError) as wrong_password:
        await auth.login(db, email="learner@example.com", password="not-the-password")

    with pytest.raises(auth.InvalidCredentialsError) as unknown_account:
        await auth.login(db, email="nobody@example.com", password="not-the-password")

    assert str(wrong_password.value) == str(unknown_account.value)


async def test_repeated_failures_are_rate_limited(db: AsyncSession) -> None:
    await make_user(db)
    for _ in range(auth.MAX_FAILURES_PER_ACCOUNT):
        with pytest.raises(auth.InvalidCredentialsError):
            await auth.login(db, email="learner@example.com", password="wrong-password-x")

    with pytest.raises(auth.RateLimitedError):
        await auth.login(db, email="learner@example.com", password="a-perfectly-fine-passphrase")


async def test_logout_revokes_the_session(db: AsyncSession) -> None:
    _, token = await auth.register(
        db, email="a@example.com", password="a-perfectly-fine-passphrase", display_name="A"
    )
    assert await auth.resolve_session(db, token) is not None
    await auth.logout(db, token)
    assert await auth.resolve_session(db, token) is None


async def test_an_unknown_token_resolves_to_nothing(db: AsyncSession) -> None:
    assert await auth.resolve_session(db, generate_session_token()) is None
    assert await auth.resolve_session(db, "") is None


async def test_a_deactivated_user_cannot_use_an_existing_session(db: AsyncSession) -> None:
    user, token = await auth.register(
        db, email="a@example.com", password="a-perfectly-fine-passphrase", display_name="A"
    )
    user.is_active = False
    await db.commit()
    assert await auth.resolve_session(db, token) is None


async def test_revoke_all_sessions_ends_every_login(db: AsyncSession) -> None:
    user = await make_user(db)
    _, second = await auth.login(
        db, email="learner@example.com", password="a-perfectly-fine-passphrase"
    )
    _, third = await auth.login(
        db, email="learner@example.com", password="a-perfectly-fine-passphrase"
    )

    revoked = await auth.revoke_all_sessions(db, user.id)
    assert revoked >= 2
    assert await auth.resolve_session(db, second) is None
    assert await auth.resolve_session(db, third) is None


async def test_sessions_store_only_a_digest(db: AsyncSession) -> None:
    _, token = await auth.register(
        db, email="a@example.com", password="a-perfectly-fine-passphrase", display_name="A"
    )
    stored = list(await db.scalars(select(Session.token_hash)))
    assert token not in stored
    assert hash_session_token(token) in stored


# ------------------------------------------------------------------ grading


async def test_grading_marks_a_perfect_attempt(seeded: AsyncSession) -> None:
    db = seeded
    user = await make_user(db)
    attempt = await learning.start_attempt(db, user, "the-machine")

    # Eager-load: async SQLAlchemy has no implicit lazy loading, so touching
    # quiz.questions on a bare query raises MissingGreenlet.
    quiz = await db.scalar(
        select(Quiz)
        .where(Quiz.id == attempt.quiz_id)
        .options(selectinload(Quiz.questions).selectinload(QuizQuestion.options))
    )
    assert quiz is not None
    perfect = {
        question.code: [option.code for option in question.options if option.is_correct]
        for question in quiz.questions
    }

    result = await learning.grade_attempt(db, user, attempt.id, perfect)
    assert result.score == 100.0
    assert result.passed
    assert result.weak_objectives == []


async def test_grading_marks_an_empty_attempt_as_zero(seeded: AsyncSession) -> None:
    db = seeded
    user = await make_user(db)
    attempt = await learning.start_attempt(db, user, "the-machine")
    result = await learning.grade_attempt(db, user, attempt.id, {})
    assert result.score == 0.0
    assert not result.passed


async def test_grading_ignores_what_the_client_claims(seeded: AsyncSession) -> None:
    """A forged submission cannot award itself a score.

    The client sends only choices. Score, pass/fail and correctness are all
    computed here from the stored key, so extra fields in the payload are
    ignored by construction.
    """
    db = seeded
    user = await make_user(db)
    attempt = await learning.start_attempt(db, user, "the-machine")

    # Every question answered with an option that is deliberately wrong,
    # plus junk keys a hostile client might try.
    quiz = await db.scalar(
        select(Quiz)
        .where(Quiz.id == attempt.quiz_id)
        .options(selectinload(Quiz.questions).selectinload(QuizQuestion.options))
    )
    assert quiz is not None
    wrong = {
        question.code: [next(option.code for option in question.options if not option.is_correct)]
        for question in quiz.questions
        if any(not option.is_correct for option in question.options)
    }
    wrong["score"] = ["100"]  # type: ignore[assignment]
    wrong["passed"] = ["true"]  # type: ignore[assignment]

    result = await learning.grade_attempt(db, user, attempt.id, wrong)
    assert result.score == 0.0
    assert not result.passed


async def test_an_attempt_cannot_be_submitted_twice(seeded: AsyncSession) -> None:
    db = seeded
    user = await make_user(db)
    attempt = await learning.start_attempt(db, user, "the-machine")
    await learning.grade_attempt(db, user, attempt.id, {})

    with pytest.raises(learning.LearningError):
        await learning.grade_attempt(db, user, attempt.id, {})


async def test_one_user_cannot_grade_another_users_attempt(seeded: AsyncSession) -> None:
    db = seeded
    owner = await make_user(db, "owner@example.com")
    intruder = await make_user(db, "intruder@example.com")
    attempt = await learning.start_attempt(db, owner, "the-machine")

    with pytest.raises(learning.NotFoundError):
        await learning.grade_attempt(db, intruder, attempt.id, {})


async def test_grading_records_every_answer(seeded: AsyncSession) -> None:
    db = seeded
    user = await make_user(db)
    attempt = await learning.start_attempt(db, user, "the-machine")
    result = await learning.grade_attempt(db, user, attempt.id, {"q1": ["a"]})

    stored = await db.scalar(
        select(func.count()).select_from(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id)
    )
    assert stored == result.total


async def test_grading_updates_progress(seeded: AsyncSession) -> None:
    db = seeded
    user = await make_user(db)
    attempt = await learning.start_attempt(db, user, "the-machine")
    await learning.grade_attempt(db, user, attempt.id, {})

    row = await db.scalar(
        select(UserProgress).where(
            UserProgress.user_id == user.id, UserProgress.entity_type == "quiz"
        )
    )
    assert row is not None
    assert row.attempts == 1
    assert row.status == "failed"


# -------------------------------------------------------- troubleshooting gate


async def _scenario(db: AsyncSession) -> TopicItem:
    topic_id = await db.scalar(select(Topic.id).where(Topic.slug == "the-machine"))
    item = await db.scalar(
        select(TopicItem).where(TopicItem.topic_id == topic_id, TopicItem.kind == "troubleshooting")
    )
    assert item is not None
    return item


async def test_solution_is_locked_until_a_hypothesis_exists(seeded: AsyncSession) -> None:
    db = seeded
    user = await make_user(db)
    scenario = await _scenario(db)

    with pytest.raises(learning.LockedError):
        await learning.reveal_solution(db, user, "the-machine", scenario.content_id)


async def test_solution_unlocks_after_a_real_hypothesis(seeded: AsyncSession) -> None:
    db = seeded
    user = await make_user(db)
    scenario = await _scenario(db)

    await learning.submit_hypothesis(
        db,
        user,
        "the-machine",
        scenario.content_id,
        "Memory-bound: si and so are sustained non-zero and swap is 4GB in use.",
    )
    solution = await learning.reveal_solution(db, user, "the-machine", scenario.content_id)
    assert solution["root_cause"]
    assert solution["method"]


async def test_a_token_hypothesis_is_refused(seeded: AsyncSession) -> None:
    """Typing 'memory' to unlock the answer defeats the purpose."""
    db = seeded
    user = await make_user(db)
    scenario = await _scenario(db)

    with pytest.raises(learning.LearningError):
        await learning.submit_hypothesis(db, user, "the-machine", scenario.content_id, "memory")

    stored = await db.scalar(
        select(func.count()).select_from(Hypothesis).where(Hypothesis.user_id == user.id)
    )
    assert stored == 0


async def test_one_users_hypothesis_does_not_unlock_it_for_another(seeded: AsyncSession) -> None:
    db = seeded
    diligent = await make_user(db, "diligent@example.com")
    lazy = await make_user(db, "lazy@example.com")
    scenario = await _scenario(db)

    await learning.submit_hypothesis(
        db,
        diligent,
        "the-machine",
        scenario.content_id,
        "Memory-bound: si and so are sustained non-zero and swap is 4GB in use.",
    )

    with pytest.raises(learning.LockedError):
        await learning.reveal_solution(db, lazy, "the-machine", scenario.content_id)


# ------------------------------------------------------------------ progress


async def test_completion_is_not_revoked_by_revisiting(seeded: AsyncSession) -> None:
    db = seeded
    user = await make_user(db)
    topic = await db.scalar(select(Topic).where(Topic.slug == "the-machine"))
    assert topic is not None

    await learning.set_progress(
        db, user, entity_type="topic", entity_id=topic.id, status="completed"
    )
    await learning.set_progress(
        db, user, entity_type="topic", entity_id=topic.id, status="in_progress"
    )

    rows = await learning.progress_map(db, user)
    assert rows[("topic", topic.id)].status == "completed"


async def test_progress_rejects_an_unknown_entity_type(seeded: AsyncSession) -> None:
    db = seeded
    user = await make_user(db)
    topic = await db.scalar(select(Topic).where(Topic.slug == "the-machine"))
    assert topic is not None

    with pytest.raises(learning.LearningError):
        await learning.set_progress(
            db, user, entity_type="nonsense", entity_id=topic.id, status="completed"
        )


async def test_dashboard_reflects_completion(seeded: AsyncSession) -> None:
    db = seeded
    user = await make_user(db)
    topic = await db.scalar(select(Topic).where(Topic.slug == "the-machine"))
    assert topic is not None

    before = await learning.dashboard(db, user)
    assert before["totals"]["topics_completed"] == 0

    await learning.set_progress(
        db, user, entity_type="topic", entity_id=topic.id, status="completed"
    )
    after = await learning.dashboard(db, user)
    assert after["totals"]["topics_completed"] == 1
    assert after["completed"][0]["slug"] == "the-machine"


async def test_a_topic_with_no_prerequisites_is_unlocked(seeded: AsyncSession) -> None:
    db = seeded
    user = await make_user(db)
    topic = await db.scalar(select(Topic).where(Topic.slug == "the-machine"))
    assert topic is not None

    gate = await learning.check_prerequisites(db, user, topic)
    assert gate.unlocked
    assert gate.reason is None
