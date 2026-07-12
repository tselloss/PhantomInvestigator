import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Icon from "../components/Icon";
import InvestigationCard from "../components/InvestigationCard";
import EmptyState from "../components/EmptyState";
import Button from "../components/Button";
import Card from "../components/Card";
import Skeleton from "../components/Skeleton";
import StatusDot from "../components/StatusDot";
import Sparkline from "../components/Sparkline";
import { integrationLabel } from "../lib/integrations";

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [recent, setRecent] = useState(null);
  const [integrations, setIntegrations] = useState(null);
  const [ai, setAi] = useState(null);

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
    fetch("/api/settings/ai")
      .then((r) => r.json())
      .then(setAi)
      .catch(() => {});
  }, []);

  const setupLoaded = ai != null && integrations != null && recent != null;
  const aiConfigured = ai?.configured;
  const toolsReady = (integrations || []).some((i) => i.configured);
  const hasInvestigated = (recent?.length ?? 0) > 0;
  const setupComplete = aiConfigured && toolsReady && hasInvestigated;
  const dailyCounts = stats?.daily?.map((d) => d.count);

  return (
    <>
      {setupLoaded && !setupComplete && (
        <section>
          <h2>Getting started</h2>
          <div className="feed-row">
            <div className="row" style={{ gap: 8 }}>
              {aiConfigured ? <Icon name="check" size={15} style={{ color: "var(--ok)" }} /> : <Icon name="zap" size={15} />}
              <span>Connect your AI provider</span>
              {aiConfigured && <span className="badge ok">{ai.provider}</span>}
            </div>
            {!aiConfigured && (
              <Link to="/settings/integrations">
                <Button variant="primary">Set up</Button>
              </Link>
            )}
          </div>

          <div className="feed-row">
            <div className="row" style={{ gap: 8 }}>
              {toolsReady ? <Icon name="check" size={15} style={{ color: "var(--ok)" }} /> : <Icon name="zap" size={15} />}
              <span>Connect a tool</span>
              {toolsReady && (
                <span className="badge ok">
                  {(integrations || []).filter((i) => i.configured).length} connected
                </span>
              )}
            </div>
            {!toolsReady && (
              <Link to="/settings/integrations">
                <Button variant="primary">Set up</Button>
              </Link>
            )}
          </div>

          <div className="feed-row">
            <div className="row" style={{ gap: 8 }}>
              {hasInvestigated ? <Icon name="check" size={15} style={{ color: "var(--ok)" }} /> : <Icon name="search" size={15} />}
              <span>Run your first investigation</span>
            </div>
            {!hasInvestigated && (
              <Link to="/investigate">
                <Button variant="primary" disabled={!aiConfigured}>Investigate</Button>
              </Link>
            )}
          </div>
        </section>
      )}

      <section>
        <h2>Last 7 days</h2>
        {stats ? (
          <div className="fault-grid">
            <StatTile icon="list" label="Investigations" value={stats.total} trend={dailyCounts} />
            <StatTile icon="check" label="Done" value={stats.by_status?.done || 0} status="ok" />
            <StatTile icon="zap" label="Partial" value={stats.by_status?.partial || 0} status="warn" />
            <StatTile icon="dollar" label="Est. cost" value={`$${(stats.total_cost_usd || 0).toFixed(2)}`} />
          </div>
        ) : (
          <div className="fault-grid">
            <Skeleton height={90} radius={12} />
            <Skeleton height={90} radius={12} />
            <Skeleton height={90} radius={12} />
            <Skeleton height={90} radius={12} />
          </div>
        )}
      </section>

      <section>
        <h2>Integration health</h2>
        {integrations?.length > 0 ? (
          <div className="integration-health-grid">
            {integrations.map((i) => (
              <StatusDot
                key={i.name}
                status={i.configured ? "ok" : "muted"}
                label={integrationLabel(i.name)}
              />
            ))}
          </div>
        ) : (
          <div className="row" style={{ gap: 16 }}>
            <Skeleton width={90} height={14} />
            <Skeleton width={90} height={14} />
            <Skeleton width={90} height={14} />
          </div>
        )}
      </section>

      <section>
        <div className="section-head">
          <h2>Recent investigations</h2>
          <Link to="/investigate">
            <Button variant="primary" icon="plus">New investigation</Button>
          </Link>
        </div>
        {recent === null && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <Skeleton height={64} radius={12} />
            <Skeleton height={64} radius={12} />
            <Skeleton height={64} radius={12} />
          </div>
        )}
        {recent?.length === 0 && (
          <EmptyState
            action={
              <Link to="/investigate">
                <Button variant="primary" icon="plus" style={{ marginTop: 10 }}>
                  Run your first investigation
                </Button>
              </Link>
            }
          >
            No investigations yet.
          </EmptyState>
        )}
        {recent?.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {recent.map((it) => (
              <InvestigationCard item={it} key={it.id} />
            ))}
          </div>
        )}
      </section>
    </>
  );
}

function StatTile({ icon, label, value, status, trend }) {
  const iconColor = status === "ok" ? "var(--ok)" : status === "warn" ? "var(--warn)" : "var(--accent)";
  return (
    <Card status={status} center>
      <div className="stat-tile-icon" style={{ color: iconColor }}>
        <Icon name={icon} size={15} />
      </div>
      <div className="stat-tile-value">{value}</div>
      <div className="placeholder" style={{ fontSize: 12.5 }}>{label}</div>
      {trend && <Sparkline data={trend} color={iconColor} />}
    </Card>
  );
}
