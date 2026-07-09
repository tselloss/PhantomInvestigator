import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Icon from "../components/Icon";

const PAGE_SIZE = 20;

export default function Investigations() {
  const [items, setItems] = useState([]);
  const [source, setSource] = useState("");
  const [status, setStatus] = useState("");
  const [deploymentId, setDeploymentId] = useState("");
  const [deployments, setDeployments] = useState([]);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/api/clients/deployments?include_archived=true")
      .then((r) => r.json())
      .then(setDeployments)
      .catch(() => {});
  }, []);

  const deploymentLabels = Object.fromEntries(
    deployments.map((d) => [d.id, `${d.client_name} / ${d.label}`])
  );

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const params = new URLSearchParams({ limit: PAGE_SIZE, offset });
      if (source) params.set("source", source);
      if (status) params.set("status", status);
      if (deploymentId) params.set("deployment_id", deploymentId);
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
  }, [source, status, deploymentId, offset]);

  return (
    <section>
      <h2>Investigations</h2>
      <div className="row" style={{ marginBottom: 16 }}>
        <div className="field">
          <label>Source</label>
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
        </div>
        <div className="field">
          <label>Status</label>
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
        <div className="field">
          <label>Project</label>
          <select
            value={deploymentId}
            onChange={(e) => {
              setOffset(0);
              setDeploymentId(e.target.value);
            }}
          >
            <option value="">All projects</option>
            {deployments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.client_name} / {d.label}
                {d.archived_at ? " (archived)" : ""}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <div className="alert err">Couldn't load investigations: {error}</div>}
      {!error && items.length === 0 && (
        <div className="empty-state">
          <Icon name="inbox" size={30} />
          <p>No investigations match these filters.</p>
        </div>
      )}

      {items.map((it) => (
        <Link className="feed-row" to={`/investigations/${it.id}`} key={it.id}>
          <div>
            <span className="feed-source">{it.source}</span>
            {it.source_ref ? ` ${it.source_ref}` : ""}
            {it.deployment_id != null && deploymentLabels[it.deployment_id] && (
              <span className="feed-meta" style={{ marginLeft: 6, marginRight: 6 }}>
                · {deploymentLabels[it.deployment_id]}
              </span>
            )}
            {" — "}
            {it.alert_text.length > 80 ? it.alert_text.slice(0, 80) + "…" : it.alert_text}
            {it.reviewed && (
              <span className="badge ok" style={{ marginLeft: 8 }}>
                reviewed
              </span>
            )}
          </div>
          <div className={"feed-status " + it.status}>{it.status}</div>
        </Link>
      ))}

      <div className="row" style={{ marginTop: 16 }}>
        <button disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}>
          <Icon name="arrowLeft" size={14} />
          Newer
        </button>
        <button disabled={items.length < PAGE_SIZE} onClick={() => setOffset((o) => o + PAGE_SIZE)}>
          Older
          <Icon name="arrowLeft" size={14} className="flip" />
        </button>
      </div>
    </section>
  );
}
