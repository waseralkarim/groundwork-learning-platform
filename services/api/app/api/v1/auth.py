"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from app.api.deps import SESSION_COOKIE, CurrentUser, Db, client_ip, verify_origin
from app.core.config import get_settings
from app.services import auth

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(verify_origin)])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=auth.MIN_PASSWORD_LENGTH, max_length=200)
    display_name: str = Field(default="", max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    """Note the absence of `password_hash`. There is no field for it."""

    id: str
    email: str
    display_name: str
    role: str


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        # httpOnly: JavaScript cannot read it, so an XSS bug cannot exfiltrate
        # the session. SameSite=Lax: the browser will not send it on
        # cross-site POSTs, which is the main CSRF vector.
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=int(auth.SESSION_ABSOLUTE_LIFETIME.total_seconds()),
        path="/",
    )


def _to_out(user) -> UserOut:
    return UserOut(
        id=str(user.id), email=user.email, display_name=user.display_name, role=user.role
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, request: Request, response: Response, db: Db) -> UserOut:
    try:
        user, token = await auth.register(
            db,
            email=body.email,
            password=body.password,
            display_name=body.display_name,
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except auth.EmailAlreadyRegisteredError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except auth.WeakPasswordError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    _set_session_cookie(response, token)
    return _to_out(user)


@router.post("/login", response_model=UserOut)
async def login(body: LoginRequest, request: Request, response: Response, db: Db) -> UserOut:
    try:
        user, token = await auth.login(
            db,
            email=body.email,
            password=body.password,
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except auth.RateLimitedError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except auth.InvalidCredentialsError as exc:
        # Identical response whether the account exists or not.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    _set_session_cookie(response, token)
    return _to_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, db: Db) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await auth.logout(db, token)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return _to_out(user)
