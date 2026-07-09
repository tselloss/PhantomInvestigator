import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Icon from "../components/Icon";

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
            <div key={i.name} className={"status-pill" + (i.configured ? "" : " faulted")} style={{ justifyContent: "center" }}>
              {i.name}: {i.configured ? "configured" : "not configured"}
            </div>
          ))}
          {integrations.length === 0 && (
            <>
              <div className="skeleton" style={{ height: 30 }} />
              <div className="skeleton" style={{ height: 30 }} />
              <div className="skeleton" style={{ height: 30 }} />
            </>
          )}
        </div>
      </section>

      <section>
        <h2>Last 7 days</h2>
        {stats ? (
          <div className="fault-grid">
            <StatTile icon="list" label="Investigations" value={stats.total} />
            <StatTile icon="check" label="Done" value={stats.by_status?.done || 0} accent="var(--ok)" />
            <StatTile icon="zap" label="Partial" value={stats.by_status?.partial || 0} accent="var(--warn)" />
            <StatTile icon="dollar" label="Est. cost" value={`$${(stats.total_cost_usd || 0).toFixed(2)}`} />
          </div>
        ) : (
          <div className="fault-grid">
            <div className="skeleton" style={{ height: 60 }} />
            <div className="skeleton" style={{ height: 60 }} />
            <div className="skeleton" style={{ height: 60 }} />
            <div className="skeleton" style={{ height: 60 }} />
          </div>
        )}
      </section>

      <section>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>Recent investigations</h2>
          <Link to="/investigate">
            <button className="primary">
              <Icon name="plus" size={14} />
              New investigation
            </button>
          </Link>
        </div>
        {recent.length === 0 && (
          <div className="empty-state">
            <Icon name="inbox" size={30} />
            <p>No investigations yet — start one above.</p>
          </div>
        )}
        {recent.map((it) => (
          <Link className="feed-row" to={`/investigations/${it.id}`} key={it.id}>
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

function StatTile({ icon, label, value, accent = "var(--accent)" }) {
  return (
    <div style={{ textAlign: "center", padding: "14px 0" }}>
      <div
        style={{
          width: 30,
          height: 30,
          margin: "0 auto 10px",
          borderRadius: 8,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "rgba(255,255,255,0.04)",
          color: accent,
        }}
      >
        <Icon name={icon} size={15} />
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.01em" }}>{value}</div>
      <div className="placeholder" style={{ fontSize: 12.5 }}>{label}</div>
    </div>
  );
}
