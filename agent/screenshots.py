"""Persistence for reporter-attached screenshots -- raw bytes captured at
investigation intake, plus the text description a one-shot vision call
extracts from them (see vision.py). Kept separate from diagnostics.py's
diagnostic_bundles table: that table's deployment_id is NOT NULL and it has
no binary column, and it's semantically a different upload (an operator
uploading on a client's behalf, vs. a reporter attaching evidence at the
moment they start an investigation).

owner_user_id is always the uploader (the logged-in user starting/about to
start an investigation) -- unlike deployment_id, which may not be chosen
yet when the screenshot is attached."""
import os

import psycopg

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5533/demo")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS investigation_screenshots (
    id SERIAL PRIMARY KEY,
    deployment_id INTEGER,
    owner_user_id INTEGER,
    investigation_id INTEGER,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    image_data BYTEA NOT NULL,
    vision_description TEXT,
    vision_status TEXT NOT NULL DEFAULT 'pending'
);
"""
# Separate ALTER for databases created before this column existed --
# CREATE TABLE IF NOT EXISTS above is a no-op against an existing table.
MIGRATE_SQL = """
ALTER TABLE investigation_screenshots ADD COLUMN IF NOT EXISTS owner_user_id INTEGER;
"""

_COLUMNS = [
    "id", "deployment_id", "owner_user_id", "investigation_id", "uploaded_at", "filename",
    "content_type", "image_data", "vision_description", "vision_status",
]
# image_data is deliberately excluded from every query below except
# get_screenshot_image -- these rows can carry several MB of bytes and
# nothing else needs them round-tripped over the wire.
_METADATA_COLUMNS = [c for c in _COLUMNS if c != "image_data"]


def _connect():
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    conn.execute(CREATE_TABLE_SQL)
    conn.execute(MIGRATE_SQL)
    return conn


def _row_to_dict(row, columns=_METADATA_COLUMNS) -> dict:
    return dict(zip(columns, row))


def store_screenshot(
    filename: str,
    content_type: str,
    image_data: bytes,
    owner_user_id: int,
    deployment_id: int | None = None,
    vision_description: str | None = None,
    vision_status: str = "pending",
) -> dict:
    with _connect() as conn:
        row = conn.execute(
            "INSERT INTO investigation_screenshots "
            "(deployment_id, owner_user_id, filename, content_type, image_data, vision_description, vision_status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING {}".format(", ".join(_METADATA_COLUMNS)),
            (deployment_id, owner_user_id, filename, content_type, image_data, vision_description, vision_status),
        ).fetchone()
    return _row_to_dict(row)


def get_screenshot(screenshot_id: int, owner_user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT {} FROM investigation_screenshots WHERE id = %s AND owner_user_id = %s".format(
                ", ".join(_METADATA_COLUMNS)
            ),
            (screenshot_id, owner_user_id),
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_screenshot_image(screenshot_id: int, owner_user_id: int) -> tuple[bytes, str] | None:
    """Dedicated single-row fetch of the actual bytes, for a future
    'view uploaded screenshot' endpoint -- kept out of get_screenshot/
    store_screenshot so ordinary metadata reads never pull image bytes."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT image_data, content_type FROM investigation_screenshots WHERE id = %s AND owner_user_id = %s",
            (screenshot_id, owner_user_id),
        ).fetchone()
    return (row[0].tobytes() if hasattr(row[0], "tobytes") else row[0], row[1]) if row else None


def link_to_investigation(screenshot_id: int, investigation_id: int) -> None:
    """Not owner-scoped: only ever called right after store_screenshot(),
    using the id it just returned, in the same request -- never reachable
    from a route with an untrusted id."""
    with _connect() as conn:
        conn.execute(
            "UPDATE investigation_screenshots SET investigation_id = %s WHERE id = %s",
            (investigation_id, screenshot_id),
        )
