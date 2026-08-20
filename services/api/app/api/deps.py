"""Shared API dependencies.

Authorisation lives here and in the service layer. A router that wants an
authenticated user asks for `CurrentUser`; there is no "authenticated therefore
allowed" default anywhere.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.identity import User
from app.services import auth

SESSION_COOKIE = "gw_session"


def client_ip(request: Request) -> str | None:
    """The client address, trusting only the proxy's own forwarded header.

    Caddy sets X-Forwarded-For after stripping any client-supplied value, so the
    last entry is the one it observed. Trusting a client-supplied full chain
    would make rate limiting trivially bypassable.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip() or None
    return request.client.host if request.client else None


async def optional_user(request: Request, db: AsyncSession = Depends(get_session)) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return await auth.resolve_session(db, token)


async def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Not signed in",
            headers={"WWW-Authenticate": "Cookie"},
        )
    return user


async def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    return user


def verify_origin(request: Request) -> None:
    """CSRF defence for state-changing requests.

    `SameSite=Lax` already blocks cross-site POSTs from a browser, but it is one
    control and browsers vary. Checking that Origin matches the Host is cheap,
    stateless, and does not require threading a token through every form.
    """
    origin = request.headers.get("origin")
    if origin is None:
        # Non-browser clients (curl, the smoke test) send no Origin. They also
        # cannot be tricked by a malicious page, which is what this defends.
        return

    host = request.headers.get("host", "")
    if not host or not origin.endswith(f"//{host}"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cross-origin request rejected")


CurrentUser = Annotated[User, Depends(current_user)]
OptionalUser = Annotated[User | None, Depends(optional_user)]
AdminUser = Annotated[User, Depends(require_admin)]
Db = Annotated[AsyncSession, Depends(get_session)]
