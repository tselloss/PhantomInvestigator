"""Session-cookie auth for real per-user accounts. Replaces the old single
shared ADMIN_USERNAME/ADMIN_PASSWORD operator credential now that this is a
publicly self-hostable tool: anyone can register their own account, and
their session carries their user id so every other module can scope data to
them (see clients.py, investigations.py, integration_credentials.py, etc).
The actual gate for protected API routes lives in main.py's AuthMiddleware,
which stashes the verified user on request.state.user; this router issues/
verifies/clears the session cookie and exposes get_current_user() for
route handlers that need "who is this"."""
import os
import time

import jwt
import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

import users

SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
SESSION_COOKIE = "phantom_session"
SESSION_TTL_SECONDS = 12 * 60 * 60
# Default secure -- disable only for plain-HTTP local dev (no TLS termination).
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "true").lower() not in ("false", "0", "")

router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


def create_token(user_id: int, username: str) -> str:
    payload = {"sub": str(user_id), "username": username, "exp": int(time.time()) + SESSION_TTL_SECONDS}
    return jwt.encode(payload, SESSION_SECRET, algorithm="HS256")


def verify_session_cookie(token: str | None) -> dict | None:
    """{"user_id": int, "username": str}, or None if missing/expired/invalid
    -- never raises, so callers can treat it as a plain "are they logged
    in" check."""
    if not token or not SESSION_SECRET:
        return None
    try:
        payload = jwt.decode(token, SESSION_SECRET, algorithms=["HS256"])
        return {"user_id": int(payload["sub"]), "username": payload.get("username", "")}
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None


def get_current_user(request: Request) -> dict:
    """FastAPI dependency for any /api/* route that needs the logged-in
    user's id -- AuthMiddleware has already verified the session and set
    request.state.user by the time a route handler runs, so this just reads
    it back (401 here would mean the middleware gate was somehow bypassed,
    not a normal path)."""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(401, "not authenticated")
    return user


def _set_session_cookie(response: Response, user: dict) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_token(user["id"], user["username"]),
        httponly=True,
        samesite="lax",
        secure=SESSION_COOKIE_SECURE,
        max_age=SESSION_TTL_SECONDS,
    )


@router.post("/register")
def register(req: RegisterRequest, response: Response):
    if not SESSION_SECRET:
        raise HTTPException(500, "SESSION_SECRET not configured")
    username = req.username.strip()
    if not username or not req.password:
        raise HTTPException(400, "username and password are required")
    try:
        user = users.create_user(username, req.password)
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "username already taken")

    try:
        from rag.ingest import main as ingest_runbooks
        ingest_runbooks(user["id"])
    except Exception:
        pass  # best-effort: e.g. EMBEDDING_API_KEY not configured yet -- shouldn't block account creation

    _set_session_cookie(response, user)
    return {"ok": True}


@router.post("/login")
def login(req: LoginRequest, response: Response):
    if not SESSION_SECRET:
        raise HTTPException(500, "SESSION_SECRET not configured")
    user = users.get_user_by_username(req.username)
    if not user or not users.verify_password(user, req.password):
        raise HTTPException(401, "invalid credentials")
    _set_session_cookie(response, user)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    user = verify_session_cookie(request.cookies.get(SESSION_COOKIE))
    if not user:
        raise HTTPException(401, "not authenticated")
    return {"id": user["user_id"], "username": user["username"]}
