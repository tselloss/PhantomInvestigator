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
      <div className="section-head">
        <h2>Runbooks</h2>
        <button className="primary" disabled={ingesting} onClick={ingest}>
          <Icon name="book" size={14} />
          {ingesting ? "Ingesting…" : "Re-ingest"}
        </button>
      </div>

      {ingestResult && (
        <div className={"alert " + (ingestResult.error ? "err" : "ok")}>
          {ingestResult.error ? `Ingest failed: ${ingestResult.error}` : `Embedded ${ingestResult.embedded_chunks} new chunks.`}
        </div>
      )}

      {error && <div className="alert err">Couldn't load runbooks: {error}</div>}
      {!error && runbooks.length === 0 && (
        <div className="empty-state">
          <Icon name="book" size={30} />
          <p>No runbooks ingested yet — click Re-ingest.</p>
        </div>
      )}

      {runbooks.map((rb) => (
        <div className="feed-row" key={rb.title}>
          <div>{rb.title}</div>
          <span className="tag">{rb.chunk_count} chunks</span>
        </div>
      ))}
    </section>
  );
}
