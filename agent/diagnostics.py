"""Persistence for uploaded diagnostic bundles -- logs/metrics/config
excerpts a support engineer submits on a client's behalf when there's no
direct query access into that client's infrastructure. owner_user_id is
denormalized from the parent deployment's owner, same pattern as every other
per-user table in this pass."""
import json
import os

import psycopg

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/demo")

MAX_EXCERPT_CHARS = 20_000  # same truncate-at-insert idiom every tool already uses

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS diagnostic_bundles (
    id SERIAL PRIMARY KEY,
    deployment_id INTEGER NOT NULL,
    owner_user_id INTEGER,
    investigation_id INTEGER,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    filename TEXT NOT NULL,
    logs_excerpt TEXT,
    metrics_excerpt TEXT,
    config_excerpt TEXT,
    extracted_manifest JSONB,
    status TEXT NOT NULL DEFAULT 'stored'
);
"""
# Separate ALTER for databases created before these columns existed --
# CREATE TABLE IF NOT EXISTS above is a no-op against an existing table.
MIGRATE_SQL = """
ALTER TABLE diagnostic_bundles ADD COLUMN IF NOT EXISTS screenshot_excerpt TEXT;
ALTER TABLE diagnostic_bundles ADD COLUMN IF NOT EXISTS owner_user_id INTEGER;
"""

_COLUMNS = [
    "id", "deployment_id", "owner_user_id", "investigation_id", "uploaded_at", "filename",
    "logs_excerpt", "metrics_excerpt", "config_excerpt", "extracted_manifest", "status",
    "screenshot_excerpt",
]


def _connect():
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    conn.execute(CREATE_TABLE_SQL)
    conn.execute(MIGRATE_SQL)
    return conn


def _row_to_dict(row) -> dict:
    return dict(zip(_COLUMNS, row))


def _truncate(text: str | None) -> str | None:
    return text if text is None else text[:MAX_EXCERPT_CHARS]


def store_bundle(
    deployment_id: int,
    owner_user_id: int,
    filename: str,
    investigation_id: int | None = None,
    logs_excerpt: str | None = None,
    metrics_excerpt: str | None = None,
    config_excerpt: str | None = None,
    extracted_manifest: dict | None = None,
    screenshot_excerpt: str | None = None,
) -> dict:
    with _connect() as conn:
        row = conn.execute(
            "INSERT INTO diagnostic_bundles "
            "(deployment_id, owner_user_id, investigation_id, filename, logs_excerpt, metrics_excerpt, config_excerpt, extracted_manifest, screenshot_excerpt) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING {}".format(", ".join(_COLUMNS)),
            (
                deployment_id, owner_user_id, investigation_id, filename,
                _truncate(logs_excerpt), _truncate(metrics_excerpt), _truncate(config_excerpt),
                json.dumps(extracted_manifest) if extracted_manifest is not None else None,
                _truncate(screenshot_excerpt),
            ),
        ).fetchone()
    return _row_to_dict(row)


def list_bundles(deployment_id: int, owner_user_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT {} FROM diagnostic_bundles WHERE deployment_id = %s AND owner_user_id = %s "
            "ORDER BY uploaded_at DESC".format(", ".join(_COLUMNS)),
            (deployment_id, owner_user_id),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_bundle(bundle_id: int, owner_user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT {} FROM diagnostic_bundles WHERE id = %s AND owner_user_id = %s".format(", ".join(_COLUMNS)),
            (bundle_id, owner_user_id),
        ).fetchone()
    return _row_to_dict(row) if row else None
