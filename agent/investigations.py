"""Persistence for investigations (manual + webhook-triggered), backing the
operator UI's history, detail, and dashboard-stats views."""
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
    reviewed BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);
"""
# Separate ALTER for databases created before the `reviewed` column existed --
# CREATE TABLE IF NOT EXISTS above is a no-op against an existing table.
MIGRATE_SQL = "ALTER TABLE investigations ADD COLUMN IF NOT EXISTS reviewed BOOLEAN NOT NULL DEFAULT false;"

_COLUMNS = ["id", "source", "source_ref", "alert_text", "status", "result", "reviewed", "created_at", "finished_at"]


def _connect():
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    conn.execute(CREATE_TABLE_SQL)
    conn.execute(MIGRATE_SQL)
    return conn


def _row_to_dict(row) -> dict:
    return dict(zip(_COLUMNS, row))


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


def list_recent(limit: int = 20, offset: int = 0, source: str | None = None, status: str | None = None) -> list[dict]:
    query = "SELECT {} FROM investigations".format(", ".join(_COLUMNS))
    clauses, params = [], []
    if source:
        clauses.append("source = %s")
        params.append(source)
    if status:
        clauses.append("status = %s")
        params.append(status)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params += [limit, offset]

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_by_id(investigation_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT {} FROM investigations WHERE id = %s".format(", ".join(_COLUMNS)),
            (investigation_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def set_reviewed(investigation_id: int, reviewed: bool) -> dict | None:
    with _connect() as conn:
        conn.execute("UPDATE investigations SET reviewed = %s WHERE id = %s", (reviewed, investigation_id))
    return get_by_id(investigation_id)


def stats(days: int = 7) -> dict:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT status, result FROM investigations WHERE created_at >= now() - (%s || ' days')::interval",
            (days,),
        ).fetchall()

    by_status: dict[str, int] = {}
    total_cost = 0.0
    for status, result in rows:
        by_status[status] = by_status.get(status, 0) + 1
        if result:
            total_cost += (result.get("usage") or {}).get("cost_usd", 0) or 0

    return {"total": len(rows), "by_status": by_status, "total_cost_usd": round(total_cost, 4), "period_days": days}
