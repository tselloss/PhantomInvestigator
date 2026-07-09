"""Persistence for the client/deployment registry -- who we sell to, which
instance is which, and (as of later slices) what we know about what each
instance is actually running. Backs the operator UI's Clients pages and lets
webhooks/investigations resolve which deployment an incident belongs to.

Every client/deployment/snapshot is owned by exactly one registered user
(owner_user_id) -- this is the primary tenancy boundary for the whole app:
everything else (investigations, diagnostic bundles, screenshots, integration
credentials) traces its ownership back to a deployment's client. The three
find_deployment_by_* lookups are the deliberate exception: they're used by
webhooks.py/checkin.py, which authenticate via a shared secret or checkin
token, not a logged-in user, so there's no owner_user_id to filter by --
whatever they resolve carries its own owner_user_id forward into whatever
gets created from it. known_releases is also unscoped: it's a shared,
global vendor release catalog, not anyone's private data."""
import json
import os
import secrets

import psycopg

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/demo")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    owner_user_id INTEGER,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deployments (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    owner_user_id INTEGER,
    label TEXT NOT NULL,
    environment TEXT NOT NULL DEFAULT 'production',
    jira_project_key TEXT,
    github_repo TEXT,
    checkin_token TEXT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deployment_snapshots (
    id SERIAL PRIMARY KEY,
    deployment_id INTEGER NOT NULL REFERENCES deployments(id),
    owner_user_id INTEGER,
    reported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source TEXT NOT NULL,
    app_version TEXT,
    build_sha TEXT,
    manifest JSONB,
    confidence REAL,
    -- Not a real FK: investigations is a separate module's table, and either
    -- module's _connect() may run first. Enforced at the application layer.
    source_investigation_id INTEGER
);

CREATE TABLE IF NOT EXISTS known_releases (
    id SERIAL PRIMARY KEY,
    version TEXT NOT NULL,
    build_sha TEXT,
    released_at TIMESTAMPTZ,
    manifest JSONB,
    notes TEXT
);
"""
# Separate ALTER for databases created before these columns existed --
# CREATE TABLE IF NOT EXISTS above is a no-op against an existing table.
# archived_at is a soft-delete marker (NULL = active): investigations,
# diagnostic bundles, and snapshots tagged with an archived client/deployment
# stay fully intact and readable by id -- this only changes what
# list_clients()/list_deployments() return by default, so investigation
# history never disappears just because the client/deployment record was
# archived. owner_user_id is nullable and unenforced at the DB level (added
# after rows already existed in dev) -- rows created before this change have
# no owner and become invisible to every user's scoped queries rather than
# being backfilled, since there's no correct automatic owner to assign them.
MIGRATE_SQL = """
ALTER TABLE clients ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS owner_user_id INTEGER;
ALTER TABLE deployments ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
ALTER TABLE deployments ADD COLUMN IF NOT EXISTS owner_user_id INTEGER;
ALTER TABLE deployment_snapshots ADD COLUMN IF NOT EXISTS owner_user_id INTEGER;
"""

_CLIENT_COLUMNS = ["id", "owner_user_id", "name", "slug", "notes", "created_at", "archived_at"]
_DEPLOYMENT_COLUMNS = [
    "id", "client_id", "owner_user_id", "label", "environment",
    "jira_project_key", "github_repo", "checkin_token", "created_at", "archived_at",
]
_SNAPSHOT_COLUMNS = [
    "id", "deployment_id", "owner_user_id", "reported_at", "source",
    "app_version", "build_sha", "manifest", "confidence", "source_investigation_id",
]
_RELEASE_COLUMNS = ["id", "version", "build_sha", "released_at", "manifest", "notes"]


def _connect():
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    conn.execute(CREATE_TABLE_SQL)
    conn.execute(MIGRATE_SQL)
    return conn


def _row_to_dict(row, columns) -> dict:
    return dict(zip(columns, row))


# ---- clients ----

def create_client(owner_user_id: int, name: str, slug: str, notes: str | None = None) -> dict:
    with _connect() as conn:
        row = conn.execute(
            "INSERT INTO clients (owner_user_id, name, slug, notes) VALUES (%s, %s, %s, %s) RETURNING {}".format(
                ", ".join(_CLIENT_COLUMNS)
            ),
            (owner_user_id, name, slug, notes),
        ).fetchone()
    return _row_to_dict(row, _CLIENT_COLUMNS)


def list_clients(owner_user_id: int, include_archived: bool = False) -> list[dict]:
    query = "SELECT {} FROM clients WHERE owner_user_id = %s".format(", ".join(_CLIENT_COLUMNS))
    params = [owner_user_id]
    if not include_archived:
        query += " AND archived_at IS NULL"
    query += " ORDER BY name"
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r, _CLIENT_COLUMNS) for r in rows]


def get_client(client_id: int, owner_user_id: int) -> dict | None:
    """Unfiltered by archived_at, unlike list_clients() -- callers that
    already have a specific id (investigations, diagnostics, the version
    registry tools) should keep resolving it regardless of archive state.
    Returns None (never raises/distinguishes) when the client exists but
    belongs to a different user -- callers should 404, not 403, so a client
    id's existence is never confirmed to someone who doesn't own it."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT {} FROM clients WHERE id = %s AND owner_user_id = %s".format(", ".join(_CLIENT_COLUMNS)),
            (client_id, owner_user_id),
        ).fetchone()
    return _row_to_dict(row, _CLIENT_COLUMNS) if row else None


def update_client(client_id: int, owner_user_id: int, name: str, notes: str | None = None) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "UPDATE clients SET name = %s, notes = %s WHERE id = %s AND owner_user_id = %s RETURNING {}".format(
                ", ".join(_CLIENT_COLUMNS)
            ),
            (name, notes, client_id, owner_user_id),
        ).fetchone()
    return _row_to_dict(row, _CLIENT_COLUMNS) if row else None


def archive_client(client_id: int, owner_user_id: int) -> dict | None:
    """Soft-delete: hides the client from list_clients() and (via
    routes/clients.py's list_all_deployments) the deployment picker, without
    touching its deployments, investigations, or diagnostic bundles -- those
    keep resolving fine by id. See archive_deployment for the equivalent on a
    single deployment."""
    with _connect() as conn:
        row = conn.execute(
            "UPDATE clients SET archived_at = now() WHERE id = %s AND owner_user_id = %s RETURNING {}".format(
                ", ".join(_CLIENT_COLUMNS)
            ),
            (client_id, owner_user_id),
        ).fetchone()
    return _row_to_dict(row, _CLIENT_COLUMNS) if row else None


# ---- deployments ----

def create_deployment(
    client_id: int,
    owner_user_id: int,
    label: str,
    environment: str = "production",
    jira_project_key: str | None = None,
    github_repo: str | None = None,
) -> dict:
    """owner_user_id is denormalized from the parent client so deployment
    lookups stay single-table -- callers (routes/clients.py) validate the
    client belongs to this user via get_client() before calling this, so
    it's always the client's own owner, never taken on faith from the
    request."""
    checkin_token = secrets.token_hex(16)
    with _connect() as conn:
        row = conn.execute(
            "INSERT INTO deployments (client_id, owner_user_id, label, environment, jira_project_key, github_repo, checkin_token) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING {}".format(", ".join(_DEPLOYMENT_COLUMNS)),
            (client_id, owner_user_id, label, environment, jira_project_key, github_repo, checkin_token),
        ).fetchone()
    return _row_to_dict(row, _DEPLOYMENT_COLUMNS)


def list_deployments(owner_user_id: int, client_id: int | None = None, include_archived: bool = False) -> list[dict]:
    query = "SELECT {} FROM deployments".format(", ".join(_DEPLOYMENT_COLUMNS))
    clauses, params = ["owner_user_id = %s"], [owner_user_id]
    if client_id is not None:
        clauses.append("client_id = %s")
        params.append(client_id)
    if not include_archived:
        clauses.append("archived_at IS NULL")
    query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC"
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r, _DEPLOYMENT_COLUMNS) for r in rows]


def get_deployment(deployment_id: int, owner_user_id: int) -> dict | None:
    """Unfiltered by archived_at -- see get_client's docstring for why."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT {} FROM deployments WHERE id = %s AND owner_user_id = %s".format(", ".join(_DEPLOYMENT_COLUMNS)),
            (deployment_id, owner_user_id),
        ).fetchone()
    return _row_to_dict(row, _DEPLOYMENT_COLUMNS) if row else None


def get_deployment_unscoped(deployment_id: int) -> dict | None:
    """Unscoped by design, for routes/checkin.py only: a deployment phoning
    home its own version doesn't have a logged-in user to scope by -- the
    deployment_id + checkin_token pair together IS the credential (the route
    compares the caller's secret against this row's own checkin_token right
    after calling this), not ownership."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT {} FROM deployments WHERE id = %s".format(", ".join(_DEPLOYMENT_COLUMNS)),
            (deployment_id,),
        ).fetchone()
    return _row_to_dict(row, _DEPLOYMENT_COLUMNS) if row else None


def update_deployment(
    deployment_id: int,
    owner_user_id: int,
    label: str,
    environment: str = "production",
    jira_project_key: str | None = None,
    github_repo: str | None = None,
) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "UPDATE deployments SET label = %s, environment = %s, jira_project_key = %s, github_repo = %s "
            "WHERE id = %s AND owner_user_id = %s RETURNING {}".format(", ".join(_DEPLOYMENT_COLUMNS)),
            (label, environment, jira_project_key, github_repo, deployment_id, owner_user_id),
        ).fetchone()
    return _row_to_dict(row, _DEPLOYMENT_COLUMNS) if row else None


def archive_deployment(deployment_id: int, owner_user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "UPDATE deployments SET archived_at = now() WHERE id = %s AND owner_user_id = %s RETURNING {}".format(
                ", ".join(_DEPLOYMENT_COLUMNS)
            ),
            (deployment_id, owner_user_id),
        ).fetchone()
    return _row_to_dict(row, _DEPLOYMENT_COLUMNS) if row else None


def find_deployment_by_jira_project(project_key: str) -> dict | None:
    """Unscoped by design -- see module docstring."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT {} FROM deployments WHERE jira_project_key = %s LIMIT 1".format(", ".join(_DEPLOYMENT_COLUMNS)),
            (project_key,),
        ).fetchone()
    return _row_to_dict(row, _DEPLOYMENT_COLUMNS) if row else None


def find_deployment_by_github_repo(repo: str) -> dict | None:
    """Unscoped by design -- see module docstring."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT {} FROM deployments WHERE github_repo = %s LIMIT 1".format(", ".join(_DEPLOYMENT_COLUMNS)),
            (repo,),
        ).fetchone()
    return _row_to_dict(row, _DEPLOYMENT_COLUMNS) if row else None


def find_deployment_by_checkin_token(token: str) -> dict | None:
    """Unscoped by design -- see module docstring."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT {} FROM deployments WHERE checkin_token = %s LIMIT 1".format(", ".join(_DEPLOYMENT_COLUMNS)),
            (token,),
        ).fetchone()
    return _row_to_dict(row, _DEPLOYMENT_COLUMNS) if row else None


# ---- deployment snapshots (version/drift ledger) ----

def record_snapshot(
    deployment_id: int,
    owner_user_id: int,
    source: str,
    app_version: str | None = None,
    build_sha: str | None = None,
    manifest: dict | None = None,
    confidence: float | None = None,
    source_investigation_id: int | None = None,
) -> dict:
    with _connect() as conn:
        row = conn.execute(
            "INSERT INTO deployment_snapshots "
            "(deployment_id, owner_user_id, source, app_version, build_sha, manifest, confidence, source_investigation_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING {}".format(", ".join(_SNAPSHOT_COLUMNS)),
            (
                deployment_id, owner_user_id, source, app_version, build_sha,
                json.dumps(manifest) if manifest is not None else None,
                confidence, source_investigation_id,
            ),
        ).fetchone()
    return _row_to_dict(row, _SNAPSHOT_COLUMNS)


def get_latest_snapshot(deployment_id: int, owner_user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT {} FROM deployment_snapshots WHERE deployment_id = %s AND owner_user_id = %s "
            "ORDER BY reported_at DESC LIMIT 1".format(", ".join(_SNAPSHOT_COLUMNS)),
            (deployment_id, owner_user_id),
        ).fetchone()
    return _row_to_dict(row, _SNAPSHOT_COLUMNS) if row else None


def list_snapshots(deployment_id: int, owner_user_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT {} FROM deployment_snapshots WHERE deployment_id = %s AND owner_user_id = %s "
            "ORDER BY reported_at DESC".format(", ".join(_SNAPSHOT_COLUMNS)),
            (deployment_id, owner_user_id),
        ).fetchall()
    return [_row_to_dict(r, _SNAPSHOT_COLUMNS) for r in rows]


# ---- known releases (vendor's own release catalog, for drift diffing --
# shared/global across all users, not per-user data) ----

def add_known_release(
    version: str,
    build_sha: str | None = None,
    released_at: str | None = None,
    manifest: dict | None = None,
    notes: str | None = None,
) -> dict:
    with _connect() as conn:
        row = conn.execute(
            "INSERT INTO known_releases (version, build_sha, released_at, manifest, notes) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING {}".format(", ".join(_RELEASE_COLUMNS)),
            (version, build_sha, released_at, json.dumps(manifest) if manifest is not None else None, notes),
        ).fetchone()
    return _row_to_dict(row, _RELEASE_COLUMNS)


def list_known_releases() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT {} FROM known_releases ORDER BY released_at DESC NULLS LAST".format(", ".join(_RELEASE_COLUMNS))
        ).fetchall()
    return [_row_to_dict(r, _RELEASE_COLUMNS) for r in rows]


BLACK_BOX_NOTE = (
    " NOTE: this deployment's version and patch history are UNKNOWN -- no prior snapshot is on "
    "record. Prioritize get_deployment_profile and the diagnostic bundle tools over assuming a "
    "version, and call record_version_fingerprint as soon as you establish any fact, even a "
    "partial or low-confidence one -- do not wait until submit_postmortem."
)


def is_black_box(deployment_id: int | None, owner_user_id: int) -> bool:
    """True when we have a deployment but no prior version/build snapshot
    for it -- the worst case this registry exists to eliminate over time."""
    return deployment_id is not None and get_latest_snapshot(deployment_id, owner_user_id) is None


def deployment_note(deployment_id: int | None, owner_user_id: int) -> str:
    """Renders 'Deployment: {client} / {label} (id {id}). ' for a known
    deployment -- this is how the model learns the actual deployment_id
    integer to pass into deployment-scoped tools (get_deployment_profile,
    search_diagnostic_bundle, etc). webhooks.py builds this note itself from
    an already-fetched deployment row (see _resolve_deployment); this is the
    equivalent for callers -- e.g. the manual /api/investigate routes -- that
    only have a deployment_id and haven't already looked up the deployment.
    Empty string when there's nothing to resolve."""
    if deployment_id is None:
        return ""
    deployment = get_deployment(deployment_id, owner_user_id)
    if not deployment:
        return ""
    client = get_client(deployment["client_id"], owner_user_id)
    client_name = client["name"] if client else f"client {deployment['client_id']}"
    return f"Deployment: {client_name} / {deployment['label']} (id {deployment_id}). "


def build_loop_alert_text(alert_text: str, investigation_id: int, deployment_id: int | None, owner_user_id: int) -> str:
    """Tools are stateless w.r.t. the investigation (identifiers come in as
    explicit LLM-supplied arguments, sourced from alert_text) -- this is how
    the model learns the investigation id and, if this deployment has no
    prior snapshot, that it's investigating black-box."""
    if deployment_id is None:
        return alert_text
    text = f"Investigation id: {investigation_id}. {alert_text}"
    if is_black_box(deployment_id, owner_user_id):
        text += BLACK_BOX_NOTE
    return text


def get_known_release_by_build_sha(build_sha: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT {} FROM known_releases WHERE build_sha = %s LIMIT 1".format(", ".join(_RELEASE_COLUMNS)),
            (build_sha,),
        ).fetchone()
    return _row_to_dict(row, _RELEASE_COLUMNS) if row else None
