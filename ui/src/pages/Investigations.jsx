import { useEffect, useState } from "react";
import Icon from "../components/Icon";
import FeedRow from "../components/FeedRow";
import EmptyState from "../components/EmptyState";

const PAGE_SIZE = 20;

function sameItems(a, b) {
  return a.length === b.length && a.every((item, i) => item.id === b[i].id && item.status === b[i].status);
}

export default function Investigations() {
  const [items, setItems] = useState([]);
  const [source, setSource] = useState("");
  const [status, setStatus] = useState("");
  const [reviewed, setReviewed] = useState("");
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
      if (reviewed) params.set("reviewed", reviewed);
      if (deploymentId) params.set("deployment_id", deploymentId);
      try {
        const res = await fetch(`/api/investigations?${params}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (cancelled) return;
        setError(null);
        // Keep the previous list in place if nothing actually changed, so a
        // background poll doesn't reset scroll position / flash the rows.
        setItems((prev) => (sameItems(prev, data) ? prev : data));
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
  }, [source, status, reviewed, deploymentId, offset]);

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
            <option value="awaiting_approval">Awaiting approval</option>
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
        <div className="field">
          <label>Reviewed</label>
          <select
            value={reviewed}
            onChange={(e) => {
              setOffset(0);
              setReviewed(e.target.value);
            }}
          >
            <option value="">All</option>
            <option value="true">Reviewed</option>
            <option value="false">Not reviewed</option>
          </select>
        </div>
      </div>

      {error && <div className="alert err">Couldn't load investigations: {error}</div>}
      {!error && items.length === 0 && (
        <EmptyState>No investigations match these filters.</EmptyState>
      )}

      {items.map((it, i) => (
        <FeedRow
          item={it}
          key={it.id}
          index={i}
          deploymentLabel={it.deployment_id != null ? deploymentLabels[it.deployment_id] : null}
        />
      ))}

      <div className="row" style={{ marginTop: 16, justifyContent: "space-between" }}>
        <button disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}>
          <Icon name="arrowLeft" size={14} />
          Newer
        </button>
        <span className="feed-meta">Page {Math.floor(offset / PAGE_SIZE) + 1}</span>
        <button disabled={items.length < PAGE_SIZE} onClick={() => setOffset((o) => o + PAGE_SIZE)}>
          Older
          <Icon name="arrowLeft" size={14} className="flip" />
        </button>
      </div>
    </section>
  );
}
