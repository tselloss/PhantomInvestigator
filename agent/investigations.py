"""Persistence for webhook-triggered investigations, so the operator UI's
activity feed has something to show for runs nobody was watching live."""
import json
import os

import psycopg

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/demo")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS investigations (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_ref TEXT,
    alert_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);
"""


def _connect():
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    conn.execute(CREATE_TABLE_SQL)
    return conn


def start(source: str, source_ref: str | None, alert_text: str) -> int:
    with _connect() as conn:
        row = conn.execute(
            "INSERT INTO investigations (source, source_ref, alert_text) VALUES (%s, %s, %s) RETURNING id",
            (source, source_ref, alert_text),
        ).fetchone()
        return row[0]


def finish(investigation_id: int, status: str, result: dict) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE investigations SET status = %s, result = %s, finished_at = now() WHERE id = %s",
            (status, json.dumps(result), investigation_id),
        )


def list_recent(limit: int = 20) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, source, source_ref, alert_text, status, result, created_at, finished_at "
            "FROM investigations ORDER BY created_at DESC LIMIT %s",
            (limit,),
        ).fetchall()
    cols = ["id", "source", "source_ref", "alert_text", "status", "result", "created_at", "finished_at"]
    return [dict(zip(cols, r)) for r in rows]
