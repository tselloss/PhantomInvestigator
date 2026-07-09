import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Icon from "../components/Icon";
import MagicBento from "../components/MagicBento";

const QUICK_ACTIONS = [
  {
    id: "investigate",
    icon: "search",
    label: "New",
    title: "Start an investigation",
    description: "Describe an incident or paste an alert and let the agent take it from there.",
    to: "/investigate",
    wide: true,
  },
  {
    id: "investigations",
    icon: "list",
    label: "History",
    title: "Investigations",
    description: "Browse past runs, postmortems, and evidence.",
    to: "/investigations",
  },
  {
    id: "clients",
    icon: "users",
    label: "Manage",
    title: "Clients",
    description: "Manage client deployments and credentials.",
    to: "/clients",
  },
  {
    id: "runbooks",
    icon: "book",
    label: "Playbooks",
    title: "Runbooks",
    description: "Guide the agent with your team's known fixes.",
    to: "/runbooks",
  },
  {
    id: "integrations",
    icon: "zap",
    label: "Connect",
    title: "Integrations",
    description: "Connect Jira, GitHub, Prometheus, Loki, and cloud providers.",
    to: "/settings/integrations",
  },
  {
    id: "demo",
    icon: "flask",
    label: "Try it",
    title: "Demo",
    description: "Run a sample investigation with seeded data.",
    to: "/demo",
  },
];

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
        <h2>Quick actions</h2>
        <MagicBento items={QUICK_ACTIONS} />
      </section>

      <section>
        <h2>Integration health</h2>
        <div className="fault-grid">
          {integrations.map((i) => (
            <div key={i.name} className="integration-tile">
              <span className="feed-source">{i.name}</span>
              <span className={"badge " + (i.configured ? "ok" : "warn")}>
                {i.configured ? "configured" : "not configured"}
              </span>
            </div>
          ))}
          {integrations.length === 0 && (
            <>
              <div className="skeleton" style={{ height: 38 }} />
              <div className="skeleton" style={{ height: 38 }} />
              <div className="skeleton" style={{ height: 38 }} />
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
            <div className="skeleton" style={{ height: 90 }} />
            <div className="skeleton" style={{ height: 90 }} />
            <div className="skeleton" style={{ height: 90 }} />
            <div className="skeleton" style={{ height: 90 }} />
          </div>
        )}
      </section>

      <section>
        <div className="section-head">
          <h2>Recent investigations</h2>
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
    <div className="stat-tile">
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
