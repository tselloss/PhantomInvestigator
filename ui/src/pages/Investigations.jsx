import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

const PAGE_SIZE = 20;

export default function Investigations() {
  const [items, setItems] = useState([]);
  const [source, setSource] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const params = new URLSearchParams({ limit: PAGE_SIZE, offset });
      if (source) params.set("source", source);
      if (status) params.set("status", status);
      try {
        const res = await fetch(`/api/investigations?${params}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) setItems(data);
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    }
    load();
    const id = setInterval(load, 10000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [source, status, offset]);

  return (
    <section>
      <h2>Investigations</h2>
      <div className="row" style={{ marginBottom: 14 }}>
        <select
          value={source}
          onChange={(e) => {
            setOffset(0);
            setSource(e.target.value);
          }}
        >
          <option value="">All sources</option>
          <option value="jira">Jira</option>
          <option value="github">GitHub</option>
          <option value="manual">Manual</option>
        </select>
        <select
          value={status}
          onChange={(e) => {
            setOffset(0);
            setStatus(e.target.value);
          }}
        >
          <option value="">All statuses</option>
          <option value="running">Running</option>
          <option value="done">Done</option>
          <option value="partial">Partial</option>
          <option value="error">Error</option>
        </select>
      </div>

      {error && <p className="placeholder">Couldn't load investigations: {error}</p>}
      {!error && items.length === 0 && <p className="placeholder">No investigations match these filters.</p>}

      {items.map((it) => (
        <Link className="feed-row" to={`/investigations/${it.id}`} key={it.id} style={{ display: "flex", textDecoration: "none", color: "inherit" }}>
          <div>
            <span className="feed-source">{it.source}</span>
            {it.source_ref ? ` ${it.source_ref}` : ""}
            {" — "}
            {it.alert_text.length > 80 ? it.alert_text.slice(0, 80) + "…" : it.alert_text}
            {it.reviewed && <span style={{ color: "var(--ok)", marginLeft: 8 }}>✓ reviewed</span>}
          </div>
          <div className={"feed-status " + it.status}>{it.status}</div>
        </Link>
      ))}

      <div className="row" style={{ marginTop: 14 }}>
        <button disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}>
          ← Newer
        </button>
        <button disabled={items.length < PAGE_SIZE} onClick={() => setOffset((o) => o + PAGE_SIZE)}>
          Older →
        </button>
      </div>
    </section>
  );
}
