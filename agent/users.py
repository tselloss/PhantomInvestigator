"""Real user accounts (registration/login), replacing the single shared
ADMIN_USERNAME/ADMIN_PASSWORD operator credential now that this is a
publicly self-hostable tool: every user gets their own account, and (see
clients.py, investigations.py, integration_credentials.py, etc.) their own
fully isolated workspace. Passwords are hashed with argon2, never stored or
compared in plaintext."""
import os

import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/demo")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_COLUMNS = ["id", "username", "password_hash", "created_at"]

_hasher = PasswordHasher()


def _connect():
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    conn.execute(CREATE_TABLE_SQL)
    return conn


def _row_to_dict(row) -> dict:
    return dict(zip(_COLUMNS, row))


def create_user(username: str, password: str) -> dict:
    """Raises psycopg.errors.UniqueViolation if username is taken -- callers
    (routes/auth.py) turn that into a 409, not a 500."""
    password_hash = _hasher.hash(password)
    with _connect() as conn:
        row = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING {}".format(
                ", ".join(_COLUMNS)
            ),
            (username, password_hash),
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


def verify_password(user: dict, password: str) -> bool:
    try:
        _hasher.verify(user["password_hash"], password)
        return True
    except VerifyMismatchError:
        return False
