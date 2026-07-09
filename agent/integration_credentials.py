"""Encrypted, DB-backed overrides for integration credentials entered via the
operator console's Integrations page. This sits on top of tools/*.py's
env-var defaults: each tool module merges a stored override (if any) over
its .env values on every call, so edits made here take effect immediately
without a server restart.

Every credential is scoped to the registered user who owns it -- a "global"
override is really "this user's own default across their clients", and a
client override belongs to whichever user owns that client. Both tables'
primary keys now include user_id; a stale dev database created before this
change (PK was just `name` / `(client_id, name)`) needs its
integration_credentials/client_integration_credentials tables dropped and
recreated -- there's no correct automatic owner to backfill onto existing
rows, matching the same call made for every other table in this pass.

Encrypted at rest with Fernet, keyed by CREDENTIALS_ENCRYPTION_KEY. Values
are never returned to the frontend -- routes/settings.py only ever reports
presence/absence (see settings.list_integrations)."""
import json
import os

import psycopg
import structlog
from cryptography.fernet import Fernet, InvalidToken

log = structlog.get_logger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/demo")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS integration_credentials (
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    encrypted_fields BYTEA NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, name)
);

CREATE TABLE IF NOT EXISTS client_integration_credentials (
    client_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    encrypted_fields BYTEA NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (client_id, name)
);
"""


def _connect():
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    conn.execute(CREATE_TABLE_SQL)
    return conn


def _fernet() -> Fernet:
    key = os.environ.get("CREDENTIALS_ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError(
            "CREDENTIALS_ENCRYPTION_KEY not configured -- generate one with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode())


def has_override(user_id: int, name: str) -> bool:
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM integration_credentials WHERE user_id = %s AND name = %s", (user_id, name)
            ).fetchone()
        return row is not None
    except Exception:
        return False


def get_credentials(user_id: int, name: str) -> dict | None:
    """The decrypted field dict, or None if no override is stored -- also
    None (not an error) when the DB is unreachable or the encryption key
    isn't configured, so tool modules transparently fall back to .env
    instead of failing an investigation over a credentials-store hiccup."""
    try:
        fernet = _fernet()
        with _connect() as conn:
            row = conn.execute(
                "SELECT encrypted_fields FROM integration_credentials WHERE user_id = %s AND name = %s",
                (user_id, name),
            ).fetchone()
        if not row:
            return None
        return json.loads(fernet.decrypt(bytes(row[0])).decode())
    except RuntimeError:
        log.warning("integration_credentials.key_not_configured", name=name, user_id=user_id)
        return None
    except InvalidToken:
        log.warning(
            "integration_credentials.decrypt_failed", name=name, user_id=user_id,
            reason="invalid_token_or_rotated_key",
        )
        return None
    except (ValueError, psycopg.Error) as e:
        log.warning("integration_credentials.lookup_failed", name=name, user_id=user_id, error=str(e))
        return None


def set_credentials(user_id: int, name: str, fields: dict) -> None:
    """Merges non-empty fields into whatever is already stored, so rotating
    a single field (e.g. just an API token) doesn't require resubmitting the
    rest -- the UI never has the existing values to resubmit anyway, since
    they're never sent back to the client once saved."""
    fernet = _fernet()
    existing = get_credentials(user_id, name) or {}
    merged = {**existing, **{k: v for k, v in fields.items() if v}}
    encrypted = fernet.encrypt(json.dumps(merged).encode())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO integration_credentials (user_id, name, encrypted_fields, updated_at) "
            "VALUES (%s, %s, %s, now()) "
            "ON CONFLICT (user_id, name) DO UPDATE SET encrypted_fields = EXCLUDED.encrypted_fields, updated_at = now()",
            (user_id, name, encrypted),
        )


def clear_credentials(user_id: int, name: str) -> None:
    with _connect() as conn:
        conn.execute(
            "DELETE FROM integration_credentials WHERE user_id = %s AND name = %s", (user_id, name)
        )


def has_client_override(client_id: int, user_id: int, name: str) -> bool:
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM client_integration_credentials WHERE client_id = %s AND user_id = %s AND name = %s",
                (client_id, user_id, name),
            ).fetchone()
        return row is not None
    except Exception:
        return False


def get_client_credentials(client_id: int, user_id: int, name: str) -> dict | None:
    """Same graceful-fallback contract as get_credentials (None on DB-down,
    missing key, or bad key -- never raises), scoped to one client's stored
    override. user_id is checked here too (not just client ownership at the
    route layer) so a deployment_id belonging to a different user can never
    resolve to their client's credentials even if a caller upstream forgot
    to validate ownership first (see resolve_credentials)."""
    try:
        fernet = _fernet()
        with _connect() as conn:
            row = conn.execute(
                "SELECT encrypted_fields FROM client_integration_credentials "
                "WHERE client_id = %s AND user_id = %s AND name = %s",
                (client_id, user_id, name),
            ).fetchone()
        if not row:
            return None
        return json.loads(fernet.decrypt(bytes(row[0])).decode())
    except RuntimeError:
        log.warning("integration_credentials.key_not_configured", name=name, client_id=client_id)
        return None
    except InvalidToken:
        log.warning(
            "integration_credentials.decrypt_failed", name=name, client_id=client_id,
            reason="invalid_token_or_rotated_key",
        )
        return None
    except (ValueError, psycopg.Error) as e:
        log.warning("integration_credentials.lookup_failed", name=name, client_id=client_id, error=str(e))
        return None


def set_client_credentials(client_id: int, user_id: int, name: str, fields: dict) -> None:
    fernet = _fernet()
    existing = get_client_credentials(client_id, user_id, name) or {}
    merged = {**existing, **{k: v for k, v in fields.items() if v}}
    encrypted = fernet.encrypt(json.dumps(merged).encode())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO client_integration_credentials (client_id, user_id, name, encrypted_fields, updated_at) "
            "VALUES (%s, %s, %s, %s, now()) "
            "ON CONFLICT (client_id, name) DO UPDATE SET "
            "user_id = EXCLUDED.user_id, encrypted_fields = EXCLUDED.encrypted_fields, updated_at = now()",
            (client_id, user_id, name, encrypted),
        )


def clear_client_credentials(client_id: int, user_id: int, name: str) -> None:
    with _connect() as conn:
        conn.execute(
            "DELETE FROM client_integration_credentials WHERE client_id = %s AND user_id = %s AND name = %s",
            (client_id, user_id, name),
        )


def resolve_credentials(
    name: str, user_id: int, deployment_id: int | None = None, client_id: int | None = None
) -> dict | None:
    """Layered lookup for tool _config() functions: this client's own
    override (if ANY fields are stored for it) wins WHOLE over the global
    override -- deliberately not a field-by-field 3-way merge, so "which
    credentials is this call using" stays answerable in one sentence. Falls
    through to the existing global override (get_credentials) when neither
    client_id nor a resolvable deployment_id is given, or the resolved client
    has no override of its own -- tool modules then merge that single result
    over their own env-var defaults per field, exactly as today.

    user_id is always the CURRENT investigation's owner -- if deployment_id
    turns out to belong to a different user (a hallucinated/malicious id in
    a tool call), clients.get_deployment(deployment_id, user_id) returns
    None, client_id stays unresolved, and this falls through to user_id's
    own global default instead of ever touching another tenant's stored
    credentials. client_id wins if both are passed; callers should only ever
    pass one (deployment_id from tool calls -- what every investigation
    carries -- client_id from the client-scoped Settings UI, which has no
    single deployment in view)."""
    if client_id is None and deployment_id is not None:
        import clients  # local import: avoid import-order coupling between the two modules
        deployment = clients.get_deployment(deployment_id, user_id)
        client_id = deployment["client_id"] if deployment else None
    if client_id is not None:
        client_creds = get_client_credentials(client_id, user_id, name)
        if client_creds:
            return client_creds
    return get_credentials(user_id, name)
