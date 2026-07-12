import { useEffect, useState } from "react";
import Button from "../components/Button";
import Card from "../components/Card";
import StatusDot from "../components/StatusDot";
import EmptyState from "../components/EmptyState";
import Skeleton from "../components/Skeleton";
import { relativeTime } from "../lib/format";
import { useToast } from "../context/ToastContext";

export default function Runbooks() {
  const toast = useToast();
  const [runbooks, setRunbooks] = useState(null);
  const [error, setError] = useState(null);
  const [ingesting, setIngesting] = useState(false);

  async function load() {
    try {
      const res = await fetch("/api/runbooks");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setRunbooks(await res.json());
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function ingest() {
    setIngesting(true);
    try {
      const res = await fetch("/api/runbooks/ingest", { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      toast.show(
        data.embedded_chunks > 0 ? `Embedded ${data.embedded_chunks} new chunks.` : "Nothing new to embed — already up to date.",
        { type: "ok" }
      );
      await load();
    } catch (e) {
      toast.show(`Ingest failed: ${e.message}`, { type: "err" });
    } finally {
      setIngesting(false);
    }
  }

  return (
    <section>
      <div className="section-head">
        <h2>Runbooks</h2>
        <Button variant="primary" icon="book" loading={ingesting} onClick={ingest}>
          {ingesting ? "Ingesting…" : "Re-ingest"}
        </Button>
      </div>
      <p className="placeholder">
        Markdown runbooks under <code>./runbooks</code> are chunked, embedded, and used as retrieval context during
        investigations. Re-ingest after editing a file — unchanged chunks are skipped automatically.
      </p>

      {error && <div className="alert err">Couldn't load runbooks: {error}</div>}

      {!error && runbooks === null && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 14 }}>
          <Skeleton height={54} radius={12} />
          <Skeleton height={54} radius={12} />
          <Skeleton height={54} radius={12} />
        </div>
      )}

      {!error && runbooks?.length === 0 && (
        <EmptyState
          icon="book"
          action={
            <Button variant="primary" icon="book" loading={ingesting} onClick={ingest} style={{ marginTop: 10 }}>
              Ingest runbooks
            </Button>
          }
        >
          No runbooks ingested yet.
        </EmptyState>
      )}

      {runbooks?.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 14 }}>
          {runbooks.map((rb) => (
            <Card key={rb.title} status={rb.last_ingested_at ? "ok" : undefined}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <div className="row" style={{ gap: 10 }}>
                  <StatusDot status={rb.last_ingested_at ? "ok" : "muted"} />
                  <span style={{ fontWeight: 600 }}>{rb.title}</span>
                  <span className="tag">{rb.chunk_count} chunks</span>
                </div>
                <span
                  className="feed-meta"
                  title={rb.last_ingested_at ? new Date(rb.last_ingested_at).toLocaleString() : undefined}
                >
                  {rb.last_ingested_at ? `ingested ${relativeTime(rb.last_ingested_at)}` : "not yet ingested"}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}
