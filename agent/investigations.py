"""Persistence for investigations (manual + webhook-triggered), backing the
operator UI's history, detail, and dashboard-stats views. Every investigation
is owned by exactly one registered user (owner_user_id) -- manual/UI triggers
set it to whoever is logged in; webhook triggers set it to the resolved
deployment's owner (see routes/webhooks.py)."""
import json
import os
from datetime import datetime, timedelta, timezone

import psycopg

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5533/demo")

# How long a just-triggered investigation counts as a "duplicate" of one
# already on record -- long enough to absorb webhook retries and accidental
# double-submits, short enough that a genuinely new incident on the same
# ticket/deployment shortly after isn't silently swallowed.
DEDUP_COOLDOWN_MINUTES = int(os.environ.get("DEDUP_COOLDOWN_MINUTES", 10))

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
# Separate ALTER for databases created before these columns existed --
# CREATE TABLE IF NOT EXISTS above is a no-op against an existing table.
# deployment_id/owner_user_id are not real FKs: deployments/users live in
# separate modules' tables, and any module's _connect() may run first.
# owner_user_id is nullable/unenforced -- rows created before this change
# have no owner and become invisible to every user's scoped queries rather
# than being backfilled, since there's no correct automatic owner for them.
# pending_action holds a not-yet-executed high-stakes write (currently only
# the webhook path's auto-post-to-Jira) awaiting operator approval -- see
# finish()/resolve_pending_action() and routes/webhooks.py. feedback_rating/
# feedback_notes are the operator's structured verdict on a finished
# postmortem (superseding the plain reviewed boolean, kept for filtering).
MIGRATE_SQL = """
ALTER TABLE investigations ADD COLUMN IF NOT EXISTS reviewed BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE investigations ADD COLUMN IF NOT EXISTS deployment_id INTEGER;
ALTER TABLE investigations ADD COLUMN IF NOT EXISTS owner_user_id INTEGER;
ALTER TABLE investigations ADD COLUMN IF NOT EXISTS pending_action JSONB;
ALTER TABLE investigations ADD COLUMN IF NOT EXISTS feedback_rating TEXT;
ALTER TABLE investigations ADD COLUMN IF NOT EXISTS feedback_notes TEXT;
ALTER TABLE investigations ADD COLUMN IF NOT EXISTS trace JSONB;
ALTER TABLE investigations ADD COLUMN IF NOT EXISTS pending_fix_action JSONB;
"""

# pending_fix_action is a second, independent high-stakes-write slot
# alongside pending_action: a proposed code fix (branch/commit/PR) awaiting
# operator approval, built by fix_proposals.build_pending_fix_action(). Kept
# as its own column rather than folding into pending_action so the existing
# jira_comment/azure_devops_comment single-dict contract (and its tests)
# never has to change shape. See resolve_pending_action/
# resolve_pending_fix_action for how the two are reconciled into `status`.
_COLUMNS = [
    "id", "source", "source_ref", "alert_text", "status", "result",
    "reviewed", "created_at", "finished_at", "deployment_id", "owner_user_id",
    "pending_action", "feedback_rating", "feedback_notes", "pending_fix_action",
]
# trace (the raw step_start/tool_call/tool_result event log, for replaying an
# investigation's timeline) is sizeable and only the detail view needs it --
# list_recent/list_with_feedback deliberately omit it to keep list payloads,
# which poll every 10s, from ballooning with every tool call's full input/output.
_DETAIL_COLUMNS = _COLUMNS + ["trace"]


def _connect():
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    conn.execute(CREATE_TABLE_SQL)
    conn.execute(MIGRATE_SQL)
    return conn


def _row_to_dict(row, columns=_COLUMNS) -> dict:
    return dict(zip(columns, row))


def start(
    source: str, source_ref: str | None, alert_text: str, owner_user_id: int, deployment_id: int | None = None
) -> int:
    with _connect() as conn:
        row = conn.execute(
            "INSERT INTO investigations (source, source_ref, alert_text, deployment_id, owner_user_id) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (source, source_ref, alert_text, deployment_id, owner_user_id),
        ).fetchone()
        return row[0]


def find_recent_duplicate(
    source: str,
    source_ref: str | None,
    deployment_id: int | None,
    alert_text: str,
    owner_user_id: int,
    cooldown_minutes: int = DEDUP_COOLDOWN_MINUTES,
) -> dict | None:
    """A newly-triggered investigation counts as a duplicate of one already
    on record if it's the same owner and (source, source_ref) -- e.g. a
    retried Jira/GitHub webhook delivery for the exact same ticket/run -- or,
    for source_ref-less manual/UI triggers, the same (source, deployment_id,
    alert_text), and the existing one started within cooldown_minutes. Two
    different users' identical alert text should never dedupe against each
    other, hence owner_user_id is always part of the match.

    Callers check this BEFORE start()/run_agent() so a genuine duplicate
    never spends a token: they return the existing investigation's current
    state instead of kicking off a new paid run."""
    if source_ref:
        query = (
            "SELECT {} FROM investigations WHERE source = %s AND source_ref = %s AND owner_user_id = %s "
            "AND created_at >= now() - (%s || ' minutes')::interval "
            "ORDER BY created_at DESC LIMIT 1"
        ).format(", ".join(_COLUMNS))
        params = (source, source_ref, owner_user_id, cooldown_minutes)
    else:
        query = (
            "SELECT {} FROM investigations WHERE source = %s AND alert_text = %s AND owner_user_id = %s "
            "AND deployment_id IS NOT DISTINCT FROM %s "
            "AND created_at >= now() - (%s || ' minutes')::interval "
            "ORDER BY created_at DESC LIMIT 1"
        ).format(", ".join(_COLUMNS))
        params = (source, alert_text, owner_user_id, deployment_id, cooldown_minutes)

    with _connect() as conn:
        row = conn.execute(query, params).fetchone()
    return _row_to_dict(row) if row else None


def finish(
    investigation_id: int, status: str, result: dict, pending_action: dict | None = None,
    pending_fix_action: dict | None = None, trace: list | None = None,
) -> None:
    """Not owner-scoped: only ever called right after start(), using the id
    start() itself just returned -- never reachable from a route with a
    user-supplied id.

    pending_action/pending_fix_action, when given, override status to
    "awaiting_approval" and record a not-yet-executed high-stakes write (a
    Jira/Azure DevOps comment, or a code fix branch+PR respectively) for an
    operator to approve or dismiss via resolve_pending_action()/
    resolve_pending_fix_action() below, instead of it firing unattended the
    moment the loop finishes. The two are independent -- either, both, or
    neither may be set on a given run.

    trace is the raw stream of step_start/tool_call/tool_result events (see
    routes powering GET /api/investigate/stream), stored so the detail page
    can replay a past run's timeline -- including a partial trace on a run
    that errored or hit budget/step limits, which is exactly the case an
    operator most wants to see replayed."""
    if pending_action is not None or pending_fix_action is not None:
        status = "awaiting_approval"
    with _connect() as conn:
        conn.execute(
            "UPDATE investigations SET status = %s, result = %s, pending_action = %s, pending_fix_action = %s, trace = %s, finished_at = now() "
            "WHERE id = %s",
            (
                status,
                json.dumps(result),
                json.dumps(pending_action) if pending_action else None,
                json.dumps(pending_fix_action) if pending_fix_action else None,
                json.dumps(trace) if trace is not None else None,
                investigation_id,
            ),
        )


def list_recent(
    owner_user_id: int,
    limit: int = 20,
    offset: int = 0,
    source: str | None = None,
    status: str | None = None,
    deployment_id: int | None = None,
    reviewed: bool | None = None,
) -> list[dict]:
    query = "SELECT {} FROM investigations".format(", ".join(_COLUMNS))
    clauses, params = ["owner_user_id = %s"], [owner_user_id]
    if source:
        clauses.append("source = %s")
        params.append(source)
    if status:
        clauses.append("status = %s")
        params.append(status)
    if deployment_id is not None:
        clauses.append("deployment_id = %s")
        params.append(deployment_id)
    if reviewed is not None:
        clauses.append("reviewed = %s")
        params.append(reviewed)
    query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params += [limit, offset]

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_with_feedback(owner_user_id: int, ratings: tuple[str, ...] = ("incorrect", "partial")) -> list[dict]:
    """Investigations an operator rated as wrong/partially wrong -- the raw
    material for evals.export_feedback, which turns these into candidate
    eval fixtures or prompt-fix input instead of letting them sit unused."""
    query = (
        "SELECT {} FROM investigations WHERE owner_user_id = %s AND feedback_rating = ANY(%s) "
        "ORDER BY created_at DESC"
    ).format(", ".join(_COLUMNS))
    with _connect() as conn:
        rows = conn.execute(query, (owner_user_id, list(ratings))).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_by_id(investigation_id: int, owner_user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT {} FROM investigations WHERE id = %s AND owner_user_id = %s".format(", ".join(_DETAIL_COLUMNS)),
            (investigation_id, owner_user_id),
        ).fetchone()
    return _row_to_dict(row, _DETAIL_COLUMNS) if row else None


def resolve_pending_action(investigation_id: int, owner_user_id: int) -> dict | None:
    """Clears a pending high-stakes write (approved-and-executed, or
    dismissed -- the caller decides which by whether it actually performs
    the action first). Only moves the investigation to "done" if
    pending_fix_action isn't still awaiting its own approval -- see
    resolve_pending_fix_action for the symmetric case."""
    with _connect() as conn:
        conn.execute(
            "UPDATE investigations SET pending_action = NULL, "
            "status = CASE WHEN pending_fix_action IS NULL THEN 'done' ELSE 'awaiting_approval' END "
            "WHERE id = %s AND owner_user_id = %s",
            (investigation_id, owner_user_id),
        )
    return get_by_id(investigation_id, owner_user_id)


def resolve_pending_fix_action(investigation_id: int, owner_user_id: int) -> dict | None:
    """Clears a pending code-fix action (approved-and-executed, or
    dismissed). Symmetric with resolve_pending_action -- only moves the
    investigation to "done" once the ticket-comment pending_action (if any)
    is also cleared."""
    with _connect() as conn:
        conn.execute(
            "UPDATE investigations SET pending_fix_action = NULL, "
            "status = CASE WHEN pending_action IS NULL THEN 'done' ELSE 'awaiting_approval' END "
            "WHERE id = %s AND owner_user_id = %s",
            (investigation_id, owner_user_id),
        )
    return get_by_id(investigation_id, owner_user_id)


def set_feedback(
    investigation_id: int, owner_user_id: int, reviewed: bool,
    feedback_rating: str | None = None, feedback_notes: str | None = None,
) -> dict | None:
    """Structured verdict on a finished postmortem -- feedback_rating is one
    of 'correct'/'partial'/'incorrect' (unenforced at the DB layer; the
    route validates it). reviewed is kept alongside for simple "has anyone
    looked at this" filtering, and is set to true whenever a rating is
    given, since rating something implies reviewing it."""
    with _connect() as conn:
        conn.execute(
            "UPDATE investigations SET reviewed = %s, feedback_rating = %s, feedback_notes = %s "
            "WHERE id = %s AND owner_user_id = %s",
            (reviewed or feedback_rating is not None, feedback_rating, feedback_notes, investigation_id, owner_user_id),
        )
    return get_by_id(investigation_id, owner_user_id)


def stats(owner_user_id: int, days: int = 7, deployment_id: int | None = None) -> dict:
    query = (
        "SELECT status, result, created_at FROM investigations "
        "WHERE owner_user_id = %s AND created_at >= now() - (%s || ' days')::interval"
    )
    params = [owner_user_id, days]
    if deployment_id is not None:
        query += " AND deployment_id = %s"
        params.append(deployment_id)
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()

    by_status: dict[str, int] = {}
    total_cost = 0.0
    daily_counts: dict[str, int] = {}
    for status, result, created_at in rows:
        by_status[status] = by_status.get(status, 0) + 1
        if result:
            total_cost += (result.get("usage") or {}).get("cost_usd", 0) or 0
        day_key = created_at.date().isoformat()
        daily_counts[day_key] = daily_counts.get(day_key, 0) + 1

    # Zero-fill every day in the window (not just days with activity) so the
    # dashboard sparkline has a fixed number of points to plot.
    today = datetime.now(timezone.utc).date()
    daily = [
        {"date": (day := today - timedelta(days=offset)).isoformat(), "count": daily_counts.get(day.isoformat(), 0)}
        for offset in range(days - 1, -1, -1)
    ]

    return {
        "total": len(rows),
        "by_status": by_status,
        "total_cost_usd": round(total_cost, 4),
        "period_days": days,
        "daily": daily,
    }


def monthly_cost_usd(owner_user_id: int) -> float:
    """Sum of result.usage.cost_usd for this owner's investigations since the
    start of the current calendar month -- the window billing.check_budget()
    enforces a spend cap against (distinct from stats()'s rolling day-window,
    which powers the Dashboard's 7-day widget, not budget enforcement)."""
    query = "SELECT result FROM investigations WHERE owner_user_id = %s AND created_at >= date_trunc('month', now())"
    with _connect() as conn:
        rows = conn.execute(query, (owner_user_id,)).fetchall()

    total = 0.0
    for (result,) in rows:
        if result:
            total += (result.get("usage") or {}).get("cost_usd", 0) or 0
    return round(total, 4)
