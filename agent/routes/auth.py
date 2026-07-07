"""Session-cookie auth for the operator console. A single shared operator
credential (ADMIN_USERNAME/ADMIN_PASSWORD) -- proportionate to an internal
tool with no user table, consistent with how Langfuse's admin user is
already configured via env vars in this same stack. The actual gate for
protected API routes lives in main.py's AuthMiddleware; this router just
issues/clears/reports the session."""
import os
import secrets
import time

import jwt
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
SESSION_COOKIE = "phantom_session"
SESSION_TTL_SECONDS = 12 * 60 * 60

router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    username: str
    password: str


def create_token(username: str) -> str:
    payload = {"sub": username, "exp": int(time.time()) + SESSION_TTL_SECONDS}
    return jwt.encode(payload, SESSION_SECRET, algorithm="HS256")


def verify_session_cookie(token: str | None) -> str | None:
    if not token or not SESSION_SECRET:
        return None
    try:
        payload = jwt.decode(token, SESSION_SECRET, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


@router.post("/login")
def login(req: LoginRequest, response: Response):
    if not (ADMIN_USERNAME and ADMIN_PASSWORD and SESSION_SECRET):
        raise HTTPException(500, "ADMIN_USERNAME/ADMIN_PASSWORD/SESSION_SECRET not configured")
    valid = secrets.compare_digest(req.username, ADMIN_USERNAME) and secrets.compare_digest(
        req.password, ADMIN_PASSWORD
    )
    if not valid:
        raise HTTPException(401, "invalid credentials")
    response.set_cookie(
        SESSION_COOKIE,
        create_token(req.username),
        httponly=True,
        samesite="lax",
        max_age=SESSION_TTL_SECONDS,
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    username = verify_session_cookie(request.cookies.get(SESSION_COOKIE))
    if not username:
        raise HTTPException(401, "not authenticated")
    return {"username": username}
