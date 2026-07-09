"""Hybrid search over runbooks: pgvector cosine similarity + Postgres
full-text search, combined via Reciprocal Rank Fusion (RRF). RRF sidesteps
having to normalize two incompatible score scales (cosine similarity vs.
ts_rank) — it only needs each list's rank order, not the raw scores.
Returns chunks with their titles so the agent can cite them."""
import os

import psycopg
from pgvector.psycopg import register_vector

from rag.ingest import embed

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/demo")

RRF_K = 60  # standard RRF constant — dampens the impact of any single rank-1 hit
TOP_K = 5

def search(query: str, user_id: int) -> str:
    try:
        [query_embedding] = embed([query], input_type="query")
    except Exception as e:
        return f"ERROR embedding query: {e}"

    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=10) as conn:
            register_vector(conn)

            vector_rows = conn.execute(
                "SELECT id, title, chunk FROM runbook_chunks WHERE owner_user_id = %s "
                "ORDER BY embedding <=> %s::vector LIMIT 10",
                (user_id, query_embedding),
            ).fetchall()

            text_rows = conn.execute(
                "SELECT id, title, chunk FROM runbook_chunks "
                "WHERE owner_user_id = %s AND to_tsvector('english', chunk) @@ plainto_tsquery('english', %s) "
                "ORDER BY ts_rank(to_tsvector('english', chunk), plainto_tsquery('english', %s)) DESC "
                "LIMIT 10",
                (user_id, query, query),
            ).fetchall()
    except Exception as e:
        return f"ERROR querying runbooks: {e}"

    scores: dict[int, float] = {}
    chunks_by_id: dict[int, tuple[str, str]] = {}
    for rank, (id_, title, chunk) in enumerate(vector_rows):
        scores[id_] = scores.get(id_, 0.0) + 1 / (RRF_K + rank)
        chunks_by_id[id_] = (title, chunk)
    for rank, (id_, title, chunk) in enumerate(text_rows):
        scores[id_] = scores.get(id_, 0.0) + 1 / (RRF_K + rank)
        chunks_by_id[id_] = (title, chunk)

    if not scores:
        return "No matching runbooks found."

    top_ids = sorted(scores, key=scores.get, reverse=True)[:TOP_K]
    return "\n\n---\n\n".join(f"[{chunks_by_id[i][0]}]\n{chunks_by_id[i][1]}" for i in top_ids)
