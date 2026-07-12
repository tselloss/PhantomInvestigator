"""Real user accounts (registration/login), replacing the single shared
ADMIN_USERNAME/ADMIN_PASSWORD operator credential now that this is a
publicly self-hostable tool: every user gets their own account, and (see
clients.py, investigations.py, integration_credentials.py, etc.) their own
fully isolated workspace. Passwords are hashed with argon2, never stored or
compared in plaintext. Users can also sign in with Google (see
routes/auth.py's /auth/google/* endpoints) -- those accounts have no
password_hash, and password accounts that later sign in with Google get
their google_id linked once Google confirms the same verified email."""
import os
from datetime import datetime, timezone

import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5533/demo")

# Bump this whenever docs/legal/terms-of-service.md changes in a way that
# needs re-acceptance -- AuthMiddleware compares it against each user's
# tos_version live on every /api/* request, so a bump takes effect for new
# requests immediately (session cookies just carry the version the user
# accepted, not a stale "still valid" bool -- see routes/auth.py).
CURRENT_TOS_VERSION = 1

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id TEXT UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS monthly_limit_usd DOUBLE PRECISION;
ALTER TABLE users ADD COLUMN IF NOT EXISTS demo_mode BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS tos_accepted_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS tos_version INTEGER;
"""

_COLUMNS = [
    "id", "username", "password_hash", "created_at", "email", "google_id", "monthly_limit_usd",
    "demo_mode", "tos_accepted_at", "tos_version",
]

_hasher = PasswordHasher()


def _connect():
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    conn.execute(CREATE_TABLE_SQL)
    return conn


def _row_to_dict(row) -> dict:
    return dict(zip(_COLUMNS, row))


def create_user(username: str, password: str, tos_accepted: bool = False) -> dict:
    """Raises psycopg.errors.UniqueViolation if username is taken -- callers
    (routes/auth.py) turn that into a 409, not a 500. tos_accepted is set by
    the caller once it has confirmed the registration form's Terms of
    Service checkbox was checked -- it stamps tos_accepted_at/tos_version
    immediately so this account never sees the first-use TermsGate popup."""
    password_hash = _hasher.hash(password)
    accepted_at = datetime.now(timezone.utc) if tos_accepted else None
    tos_version = CURRENT_TOS_VERSION if tos_accepted else None
    with _connect() as conn:
        row = conn.execute(
            "INSERT INTO users (username, password_hash, tos_accepted_at, tos_version) "
            "VALUES (%s, %s, %s, %s) RETURNING {}".format(", ".join(_COLUMNS)),
            (username, password_hash, accepted_at, tos_version),
        ).fetchone()
    return _row_to_dict(row)


def get_user_by_username(username: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT {} FROM users WHERE username = %s".format(", ".join(_COLUMNS)),
            (username,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT {} FROM users WHERE id = %s".format(", ".join(_COLUMNS)),
            (user_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_user_by_google_id(google_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT {} FROM users WHERE google_id = %s".format(", ".join(_COLUMNS)),
            (google_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_user_by_email(email: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT {} FROM users WHERE email = %s".format(", ".join(_COLUMNS)),
            (email,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def create_google_user(username: str, email: str, google_id: str) -> dict:
    """Raises psycopg.errors.UniqueViolation if username is taken -- callers
    (routes/auth.py) retry with a suffixed username rather than failing the
    login. No password_hash: this account can only sign in via Google."""
    with _connect() as conn:
        row = conn.execute(
            "INSERT INTO users (username, email, google_id) VALUES (%s, %s, %s) RETURNING {}".format(
                ", ".join(_COLUMNS)
            ),
            (username, email, google_id),
        ).fetchone()
    return _row_to_dict(row)


def link_google_id(user_id: int, google_id: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE users SET google_id = %s WHERE id = %s", (google_id, user_id))


def accept_terms(user_id: int) -> None:
    """Stamps tos_accepted_at/tos_version -- called the first time a user
    confirms the Terms of Service popup (Google sign-ins, which have no
    registration-form checkbox; see /register's accept_terms field for the
    password-account path) and again whenever CURRENT_TOS_VERSION is bumped
    and an existing user re-confirms. Always records a fresh timestamp: a
    call here means accepting whatever version is current *now*, which may
    be a re-acceptance of updated terms, not just the first one."""
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET tos_accepted_at = now(), tos_version = %s WHERE id = %s",
            (CURRENT_TOS_VERSION, user_id),
        )


def update_monthly_limit(user_id: int, limit_usd: float | None) -> None:
    with _connect() as conn:
        conn.execute("UPDATE users SET monthly_limit_usd = %s WHERE id = %s", (limit_usd, user_id))


def get_demo_mode(user_id: int) -> bool:
    """Whether tools/*.py should fall back to agent/demo_data.py's canned
    responses for any integration this user hasn't actually configured --
    lets a live demo show the full tool belt without real credentials.
    Never affects an integration that *is* configured; real credentials
    always win."""
    user = get_user_by_id(user_id)
    return bool(user and user.get("demo_mode"))


def update_demo_mode(user_id: int, enabled: bool) -> None:
    with _connect() as conn:
        conn.execute("UPDATE users SET demo_mode = %s WHERE id = %s", (enabled, user_id))


def verify_password(user: dict, password: str) -> bool:
    if not user.get("password_hash"):
        return False
    try:
        _hasher.verify(user["password_hash"], password)
        return True
    except VerifyMismatchError:
        return False
