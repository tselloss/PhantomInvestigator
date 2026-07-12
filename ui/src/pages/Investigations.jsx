import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import Icon from "../components/Icon";
import InvestigationRow from "../components/InvestigationRow";
import EmptyState from "../components/EmptyState";
import Button from "../components/Button";
import Skeleton from "../components/Skeleton";
import { useToast } from "../context/ToastContext";

const PAGE_SIZE = 20;

const SOURCES = [
  { value: "", label: "All sources" },
  { value: "jira", label: "Jira" },
  { value: "github", label: "GitHub" },
  { value: "manual", label: "Manual" },
];
const STATUSES = [
  { value: "", label: "All statuses" },
  { value: "running", label: "Running" },
  { value: "awaiting_approval", label: "Awaiting approval" },
  { value: "done", label: "Done" },
  { value: "partial", label: "Partial" },
  { value: "error", label: "Error" },
];
const REVIEWED = [
  { value: "", label: "All" },
  { value: "false", label: "Not reviewed" },
  { value: "true", label: "Reviewed" },
];

function sameItems(a, b) {
  return a.length === b.length && a.every((item, i) => item.id === b[i].id && item.status === b[i].status);
}

export default function Investigations() {
  const toast = useToast();
  const [items, setItems] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [source, setSource] = useState("");
  const [status, setStatus] = useState("");
  const [reviewed, setReviewed] = useState("");
  const [deploymentId, setDeploymentId] = useState("");
  const [deployments, setDeployments] = useState([]);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState(null);
  const [sortKey, setSortKey] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc");

  useEffect(() => {
    fetch("/api/clients/deployments?include_archived=true")
      .then((r) => r.json())
      .then(setDeployments)
      .catch(() => {});
  }, []);

  const deploymentLabels = Object.fromEntries(deployments.map((d) => [d.id, `${d.client_name} / ${d.label}`]));

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
        setLoaded(true);
        // Keep the previous list in place if nothing actually changed, so a
        // background poll doesn't reset scroll position / flash the rows.
        setItems((prev) => (sameItems(prev, data) ? prev : data));
      } catch (e) {
        if (!cancelled) {
          setError(e.message);
          setLoaded(true);
        }
      }
    }
    load();
    const id = setInterval(load, 10000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [source, status, reviewed, deploymentId, offset]);

  const sorted = useMemo(() => {
    const copy = [...items];
    copy.sort((a, b) => {
      let av = a[sortKey];
      let bv = b[sortKey];
      if (sortKey === "created_at") {
        av = new Date(av).getTime();
        bv = new Date(bv).getTime();
      }
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return copy;
  }, [items, sortKey, sortDir]);

  function toggleSort(key) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  async function markReviewed(id) {
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, reviewed: true } : it)));
    try {
      const res = await fetch(`/api/investigations/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reviewed: true }),
      });
      if (!res.ok) throw new Error();
      toast.show("Marked as reviewed.", { type: "ok" });
    } catch {
      setItems((prev) => prev.map((it) => (it.id === id ? { ...it, reviewed: false } : it)));
      toast.show("Couldn't mark as reviewed — try again.", { type: "err" });
    }
  }

  function setFilter(setter) {
    return (value) => {
      setOffset(0);
      setter(value);
    };
  }

  function clearFilters() {
    setOffset(0);
    setSource("");
    setStatus("");
    setReviewed("");
    setDeploymentId("");
  }

  const filtersActive = Boolean(source || status || reviewed || deploymentId);

  function SortHeader({ label, sortKeyName }) {
    const active = sortKey === sortKeyName;
    return (
      <th className="sortable" onClick={() => toggleSort(sortKeyName)}>
        {label}
        {active && (
          <Icon
            name="chevron"
            size={11}
            className="sort-icon"
            style={{ transform: sortDir === "asc" ? "rotate(-90deg)" : "rotate(90deg)" }}
          />
        )}
      </th>
    );
  }

  return (
    <section>
      <h2>Investigations</h2>

      <div className="filter-chip-rows">
        <div className="subtabs">
          {SOURCES.map((s) => (
            <button
              key={s.value || "all"}
              type="button"
              className={"subtab" + (source === s.value ? " active" : "")}
              onClick={() => setFilter(setSource)(s.value)}
            >
              {s.label}
            </button>
          ))}
        </div>
        <div className="subtabs">
          {STATUSES.map((s) => (
            <button
              key={s.value || "all"}
              type="button"
              className={"subtab" + (status === s.value ? " active" : "")}
              onClick={() => setFilter(setStatus)(s.value)}
            >
              {s.label}
            </button>
          ))}
        </div>
        <div className="subtabs">
          {REVIEWED.map((r) => (
            <button
              key={r.value || "all"}
              type="button"
              className={"subtab" + (reviewed === r.value ? " active" : "")}
              onClick={() => setFilter(setReviewed)(r.value)}
            >
              {r.label}
            </button>
          ))}
        </div>
        <select className="deployment-filter" value={deploymentId} onChange={(e) => setFilter(setDeploymentId)(e.target.value)}>
          <option value="">All projects</option>
          {deployments.map((d) => (
            <option key={d.id} value={d.id}>
              {d.client_name} / {d.label}
              {d.archived_at ? " (archived)" : ""}
            </option>
          ))}
        </select>
      </div>

      {error && <div className="alert err">Couldn't load investigations: {error}</div>}

      {!error && !loaded && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <Skeleton height={38} />
          <Skeleton height={38} />
          <Skeleton height={38} />
        </div>
      )}

      {!error && loaded && items.length === 0 && (
        <EmptyState
          action={
            filtersActive ? (
              <Button variant="ghost" onClick={clearFilters} style={{ marginTop: 10 }}>
                Clear filters
              </Button>
            ) : (
              <Link to="/investigate">
                <Button variant="primary" icon="search" style={{ marginTop: 10 }}>
                  Run an investigation
                </Button>
              </Link>
            )
          }
        >
          {filtersActive ? "No investigations match these filters." : "No investigations yet."}
        </EmptyState>
      )}

      {items.length > 0 && (
        <div className="inv-table-wrap">
          <table className="inv-table">
            <thead>
              <tr>
                <th className="inv-td-status-bar" />
                <SortHeader label="Source" sortKeyName="source" />
                <th>Alert</th>
                <th>Project</th>
                <SortHeader label="Status" sortKeyName="status" />
                <SortHeader label="Time" sortKeyName="created_at" />
                <th />
              </tr>
            </thead>
            <tbody>
              {sorted.map((it) => (
                <InvestigationRow
                  key={it.id}
                  item={it}
                  showDeployment
                  deploymentLabel={it.deployment_id != null ? deploymentLabels[it.deployment_id] : null}
                  onMarkReviewed={markReviewed}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="row" style={{ marginTop: 16, justifyContent: "space-between" }}>
        <Button disabled={offset === 0} icon="arrowLeft" onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}>
          Newer
        </Button>
        <span className="feed-meta">Page {Math.floor(offset / PAGE_SIZE) + 1}</span>
        <Button disabled={items.length < PAGE_SIZE} onClick={() => setOffset((o) => o + PAGE_SIZE)}>
          Older
          <Icon name="arrowLeft" size={14} className="flip" />
        </Button>
      </div>
    </section>
  );
}
