"""runbooks/*.md -> chunks -> embeddings -> pgvector.

Chunks by markdown '## ' section, prepending the doc title so each chunk is
self-contained. Embeddings come from Voyage AI (voyage-3, 1024-dim — matches
the embedding column below). Re-running skips chunks already embedded via a
content-hash cache.
"""
import hashlib
import os
import re
from pathlib import Path

import httpx
import psycopg
from pgvector.psycopg import register_vector

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/demo")
EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "voyage-3")
EMBEDDING_DIM = 1024

RUNBOOKS_DIR = Path(__file__).resolve().parent.parent / "runbooks"

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS runbook_chunks (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    chunk TEXT NOT NULL,
    content_hash TEXT UNIQUE NOT NULL,
    embedding vector({EMBEDDING_DIM})
);
"""

def chunk_markdown(text: str, title: str) -> list[str]:
    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    return [f"# {title}\n\n{s.strip()}" for s in sections if s.strip()]

def embed(texts: list[str], input_type: str = "document") -> list[list[float]]:
    resp = httpx.post(
        "https://api.voyageai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {EMBEDDING_API_KEY}"},
        json={"input": texts, "model": EMBEDDING_MODEL, "input_type": input_type},
        timeout=30.0,
    )
    resp.raise_for_status()
    return [d["embedding"] for d in resp.json()["data"]]

def main() -> int:
    """Returns the number of newly-embedded chunks (0 if nothing changed)."""
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(conn)
        conn.execute(CREATE_TABLE_SQL)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS runbook_chunks_embedding_idx "
            "ON runbook_chunks USING hnsw (embedding vector_cosine_ops)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS runbook_chunks_fts_idx "
            "ON runbook_chunks USING GIN (to_tsvector('english', chunk))"
        )

        to_embed = []
        for path in sorted(RUNBOOKS_DIR.glob("*.md")):
            title = path.stem.replace("-", " ")
            for chunk in chunk_markdown(path.read_text(), title):
                content_hash = hashlib.sha256(chunk.encode()).hexdigest()
                exists = conn.execute(
                    "SELECT 1 FROM runbook_chunks WHERE content_hash = %s", (content_hash,)
                ).fetchone()
                if not exists:
                    to_embed.append((title, chunk, content_hash))

        if not to_embed:
            print("Nothing new to embed.")
            return 0

        embeddings = embed([c[1] for c in to_embed])
        for (title, chunk, content_hash), embedding in zip(to_embed, embeddings):
            conn.execute(
                "INSERT INTO runbook_chunks (title, chunk, content_hash, embedding) "
                "VALUES (%s, %s, %s, %s)",
                (title, chunk, content_hash, embedding),
            )
        print(f"Embedded {len(to_embed)} new chunks.")
        return len(to_embed)


def list_runbooks() -> list[dict]:
    """Distinct titles + chunk counts. Falls back to the raw markdown filenames
    if nothing has been ingested into Postgres yet."""
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=10) as conn:
            rows = conn.execute(
                "SELECT title, COUNT(*) FROM runbook_chunks GROUP BY title ORDER BY title"
            ).fetchall()
        if rows:
            return [{"title": title, "chunk_count": count} for title, count in rows]
    except Exception:
        pass
    return [{"title": path.stem.replace("-", " "), "chunk_count": 0} for path in sorted(RUNBOOKS_DIR.glob("*.md"))]


if __name__ == "__main__":
    main()
