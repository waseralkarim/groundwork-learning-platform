"""Authentication service.

All authorisation decisions happen here and in the dependencies that call it —
never in a router, and never on the frontend.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    password_needs_rehash,
    verify_password,
    waste_time_like_a_real_verification,
)
from app.models.identity import AuditLog, LoginAttempt, Session, User

log = get_logger(__name__)

SESSION_IDLE_TIMEOUT = timedelta(days=14)
SESSION_ABSOLUTE_LIFETIME = timedelta(days=90)

# Rate limits. Per-account limits stop credential stuffing against one target;
# per-IP limits stop a spray across many accounts. Both are needed.
MAX_FAILURES_PER_ACCOUNT = 8
MAX_FAILURES_PER_IP = 30
RATE_LIMIT_WINDOW = timedelta(minutes=15)

MIN_PASSWORD_LENGTH = 12


class AuthError(Exception):
    """Base for authentication failures that are safe to surface."""


class InvalidCredentialsError(AuthError):
    """Deliberately identical for unknown-account and wrong-password."""


class RateLimitedError(AuthError):
    pass


class EmailAlreadyRegisteredError(AuthError):
    pass


class WeakPasswordError(AuthError):
    pass


def _normalise_email(email: str) -> str:
    return email.strip().lower()


async def _record_attempt(
    session: AsyncSession, email: str, ip: str | None, *, succeeded: bool
) -> None:
    session.add(LoginAttempt(email=email, ip=ip, succeeded=succeeded))


async def _check_rate_limit(session: AsyncSession, email: str, ip: str | None) -> None:
    since = datetime.now(UTC) - RATE_LIMIT_WINDOW

    account_failures = await session.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(
            LoginAttempt.email == email,
            LoginAttempt.succeeded.is_(False),
            LoginAttempt.at >= since,
        )
    )
    if (account_failures or 0) >= MAX_FAILURES_PER_ACCOUNT:
        raise RateLimitedError("too many failed attempts for this account")

    if ip:
        ip_failures = await session.scalar(
            select(func.count())
            .select_from(LoginAttempt)
            .where(
                LoginAttempt.ip == ip,
                LoginAttempt.succeeded.is_(False),
                LoginAttempt.at >= since,
            )
        )
        if (ip_failures or 0) >= MAX_FAILURES_PER_IP:
            raise RateLimitedError("too many failed attempts from this address")


async def register(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, str]:
    email = _normalise_email(email)

    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")

    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise EmailAlreadyRegisteredError("that email is already registered")

    existing_users = await db.scalar(select(func.count()).select_from(User))
    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name.strip() or email.split("@")[0],
        # The first account to register owns the instance. This is a
        # single-operator platform; a public deployment would need an invite
        # flow instead, and that is called out in the security doc.
        role="admin" if existing_users == 0 else "learner",
    )
    db.add(user)
    await db.flush()

    db.add(AuditLog(actor_id=user.id, action="user.register", target=email))
    token = await _create_session(db, user, ip=ip, user_agent=user_agent)
    await db.commit()

    log.info("user_registered", user_id=str(user.id), role=user.role)
    return user, token


async def login(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, str]:
    email = _normalise_email(email)
    await _check_rate_limit(db, email, ip)

    user = await db.scalar(select(User).where(User.email == email))

    if user is None:
        # Burn comparable time so the response does not reveal whether the
        # account exists.
        waste_time_like_a_real_verification()
        await _record_attempt(db, email, ip, succeeded=False)
        await db.commit()
        raise InvalidCredentialsError("email or password is incorrect")

    if not user.is_active or not verify_password(password, user.password_hash):
        await _record_attempt(db, email, ip, succeeded=False)
        db.add(AuditLog(actor_id=user.id, action="auth.login_failed", target=email))
        await db.commit()
        raise InvalidCredentialsError("email or password is incorrect")

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    user.last_login_at = datetime.now(UTC)
    await _record_attempt(db, email, ip, succeeded=True)
    db.add(AuditLog(actor_id=user.id, action="auth.login", target=email))

    token = await _create_session(db, user, ip=ip, user_agent=user_agent)
    await db.commit()

    log.info("user_logged_in", user_id=str(user.id))
    return user, token


async def _create_session(
    db: AsyncSession, user: User, *, ip: str | None, user_agent: str | None
) -> str:
    token = generate_session_token()
    now = datetime.now(UTC)
    db.add(
        Session(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=now + SESSION_IDLE_TIMEOUT,
            absolute_expires_at=now + SESSION_ABSOLUTE_LIFETIME,
            ip=ip,
            user_agent=(user_agent or "")[:400] or None,
        )
    )
    return token


async def resolve_session(db: AsyncSession, token: str) -> User | None:
    """Look up the user for a session token, sliding its expiry forward.

    Returns None for anything unusable — unknown, expired, revoked, or belonging
    to a deactivated user — without distinguishing between them.
    """
    if not token:
        return None

    now = datetime.now(UTC)
    session = await db.scalar(
        select(Session).where(Session.token_hash == hash_session_token(token))
    )

    if session is None or session.revoked_at is not None:
        return None
    if session.expires_at <= now or session.absolute_expires_at <= now:
        return None

    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None

    # Slide the idle window, but never past the absolute ceiling. Without the
    # ceiling a stolen token stays valid forever as long as it keeps being used.
    new_expiry = min(now + SESSION_IDLE_TIMEOUT, session.absolute_expires_at)
    if new_expiry > session.expires_at:
        session.expires_at = new_expiry
        await db.commit()

    return user


async def logout(db: AsyncSession, token: str) -> None:
    session = await db.scalar(
        select(Session).where(Session.token_hash == hash_session_token(token))
    )
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        db.add(AuditLog(actor_id=session.user_id, action="auth.logout"))
        await db.commit()


async def revoke_all_sessions(db: AsyncSession, user_id) -> int:
    """Used on password change, and available for incident response."""
    now = datetime.now(UTC)
    sessions = list(
        await db.scalars(
            select(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None))
        )
    )
    for session in sessions:
        session.revoked_at = now
    db.add(AuditLog(actor_id=user_id, action="auth.revoke_all", detail={"count": len(sessions)}))
    await db.commit()
    return len(sessions)
