"""Session-cookie auth for real per-user accounts. Replaces the old single
shared ADMIN_USERNAME/ADMIN_PASSWORD operator credential now that this is a
publicly self-hostable tool: anyone can register their own account, and
their session carries their user id so every other module can scope data to
them (see clients.py, investigations.py, integration_credentials.py, etc).
The actual gate for protected API routes lives in main.py's AuthMiddleware,
which stashes the verified user on request.state.user; this router issues/
verifies/clears the session cookie and exposes get_current_user() for
route handlers that need "who is this". /auth/google/* below adds Google
sign-in as a second, optional way to get that same session cookie -- each
self-hosted instance configures its own Google OAuth client via env vars."""
import os
import secrets
import time
from urllib.parse import urlencode

import httpx
import jwt
import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

import users

SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
SESSION_COOKIE = "phantom_session"
SESSION_TTL_SECONDS = 12 * 60 * 60
# Default secure -- disable only for plain-HTTP local dev (no TLS termination).
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "true").lower() not in ("false", "0", "")

# Google sign-in -- each self-hosted instance registers its own OAuth client
# in Google Cloud Console (redirect URI must match GOOGLE_REDIRECT_URI
# exactly, ngrok URL and all -- see the tunnel gotcha in CLAUDE.md).
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "")
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
OAUTH_STATE_COOKIE = "phantom_oauth_state"
OAUTH_STATE_TTL_SECONDS = 10 * 60

router = APIRouter(prefix="/auth")


def _google_configured() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI)


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


@router.get("/google/status")
def google_status():
    """Unauthenticated so the logged-out login/register pages can decide
    whether to render the "Continue with Google" button -- not every
    self-hosted instance will have a Google OAuth client configured."""
    return {"enabled": _google_configured()}


@router.get("/google/login")
def google_login():
    if not SESSION_SECRET:
        raise HTTPException(500, "SESSION_SECRET not configured")
    if not _google_configured():
        raise HTTPException(500, "Google sign-in is not configured")

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    redirect = RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")
    redirect.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        httponly=True,
        samesite="lax",
        secure=SESSION_COOKIE_SECURE,
        max_age=OAUTH_STATE_TTL_SECONDS,
    )
    return redirect


def _username_from_email(email: str) -> str:
    return email.split("@")[0]


@router.get("/google/callback")
def google_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    failure = RedirectResponse("/login?error=google_failed")
    failure.delete_cookie(OAUTH_STATE_COOKIE)

    cookie_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if error or not code or not state or not cookie_state or state != cookie_state:
        return failure
    if not (SESSION_SECRET and _google_configured()):
        return failure

    try:
        token_resp = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            timeout=10.0,
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        userinfo_resp = httpx.get(
            GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10.0
        )
        userinfo_resp.raise_for_status()
        info = userinfo_resp.json()
    except (httpx.HTTPError, KeyError, ValueError):
        return failure

    google_id = info.get("sub")
    email = info.get("email")
    if not google_id or not email or not info.get("email_verified"):
        return failure

    user = users.get_user_by_google_id(google_id)
    is_new = False
    if not user:
        user = users.get_user_by_email(email)
        if user:
            users.link_google_id(user["id"], google_id)
        else:
            base_username = _username_from_email(email)
            try:
                user = users.create_google_user(base_username, email, google_id)
            except psycopg.errors.UniqueViolation:
                user = users.create_google_user(f"{base_username}-{secrets.token_hex(3)}", email, google_id)
            is_new = True

    if is_new:
        try:
            from rag.ingest import main as ingest_runbooks
            ingest_runbooks(user["id"])
        except Exception:
            pass  # best-effort: e.g. EMBEDDING_API_KEY not configured yet -- shouldn't block account creation

    success = RedirectResponse("/dashboard")
    success.delete_cookie(OAUTH_STATE_COOKIE)
    _set_session_cookie(success, user)
    return success
