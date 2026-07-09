import { useEffect, useState } from "react";
import Icon from "../components/Icon";

export default function Runbooks() {
  const [runbooks, setRunbooks] = useState([]);
  const [error, setError] = useState(null);
  const [ingesting, setIngesting] = useState(false);
  const [ingestResult, setIngestResult] = useState(null);

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
    setIngestResult(null);
    try {
      const res = await fetch("/api/runbooks/ingest", { method: "POST" });
      const data = await res.json();
      setIngestResult(data);
      await load();
    } catch (e) {
      setIngestResult({ error: e.message });
    } finally {
      setIngesting(false);
    }
  }

  return (
    <section>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>Runbooks</h2>
        <button className="primary" disabled={ingesting} onClick={ingest}>
          <Icon name="book" size={14} />
          {ingesting ? "Ingesting…" : "Re-ingest"}
        </button>
      </div>

      {ingestResult && (
        <p className="placeholder">
          {ingestResult.error ? `Ingest failed: ${ingestResult.error}` : `Embedded ${ingestResult.embedded_chunks} new chunks.`}
        </p>
      )}

      {error && <p className="placeholder">Couldn't load runbooks: {error}</p>}
      {!error && runbooks.length === 0 && (
        <div className="empty-state">
          <Icon name="book" size={30} />
          <p>No runbooks ingested yet — click Re-ingest.</p>
        </div>
      )}

      {runbooks.map((rb) => (
        <div className="feed-row" key={rb.title}>
          <div>{rb.title}</div>
          <div className="feed-meta">{rb.chunk_count} chunks</div>
        </div>
      ))}
    </section>
  );
}
