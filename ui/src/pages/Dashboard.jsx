import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [recent, setRecent] = useState([]);
  const [integrations, setIntegrations] = useState([]);

  useEffect(() => {
    fetch("/api/investigations/stats")
      .then((r) => r.json())
      .then(setStats)
      .catch(() => {});
    fetch("/api/investigations?limit=5")
      .then((r) => r.json())
      .then(setRecent)
      .catch(() => {});
    fetch("/api/settings/integrations")
      .then((r) => r.json())
      .then(setIntegrations)
      .catch(() => {});
  }, []);

  return (
    <>
      <section>
        <h2>Integration health</h2>
        <div className="fault-grid">
          {integrations.map((i) => (
            <div key={i.name} className={"status-pill" + (i.configured ? "" : " faulted")} style={{ textAlign: "center" }}>
              {i.name}: {i.configured ? "configured" : "not configured"}
            </div>
          ))}
          {integrations.length === 0 && <p className="placeholder">Loading…</p>}
        </div>
      </section>

      <section>
        <h2>Last 7 days</h2>
        {stats ? (
          <div className="fault-grid">
            <StatTile label="Investigations" value={stats.total} />
            <StatTile label="Done" value={stats.by_status?.done || 0} />
            <StatTile label="Partial" value={stats.by_status?.partial || 0} />
            <StatTile label="Est. cost" value={`$${(stats.total_cost_usd || 0).toFixed(2)}`} />
          </div>
        ) : (
          <p className="placeholder">Loading…</p>
        )}
      </section>

      <section>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>Recent investigations</h2>
          <Link to="/investigate">
            <button className="primary">+ New investigation</button>
          </Link>
        </div>
        {recent.length === 0 && <p className="placeholder">No investigations yet.</p>}
        {recent.map((it) => (
          <Link
            className="feed-row"
            to={`/investigations/${it.id}`}
            key={it.id}
            style={{ display: "flex", textDecoration: "none", color: "inherit" }}
          >
            <div>
              <span className="feed-source">{it.source}</span>
              {it.source_ref ? ` ${it.source_ref}` : ""}
              {" — "}
              {it.alert_text.length > 80 ? it.alert_text.slice(0, 80) + "…" : it.alert_text}
            </div>
            <div className={"feed-status " + it.status}>{it.status}</div>
          </Link>
        ))}
      </section>
    </>
  );
}

function StatTile({ label, value }) {
  return (
    <div style={{ textAlign: "center", padding: "12px 0" }}>
      <div style={{ fontSize: 28, fontWeight: 600 }}>{value}</div>
      <div className="placeholder">{label}</div>
    </div>
  );
}
