import { useNavigate } from "react-router-dom";
import Icon from "./Icon";
import Card from "./Card";
import { relativeTime, truncate } from "../lib/format";

const STATUS_META = {
  done: { icon: "check", color: "var(--ok)", cardStatus: "ok" },
  partial: { icon: "zap", color: "var(--warn)", cardStatus: "warn" },
  awaiting_approval: { icon: "inbox", color: "var(--warn)", cardStatus: "warn" },
  error: { icon: "x", color: "var(--err)", cardStatus: "err" },
  running: { icon: "search", color: "var(--accent)", cardStatus: "accent" },
};

export default function InvestigationCard({ item }) {
  const navigate = useNavigate();
  const meta = STATUS_META[item.status] || { icon: "search", color: "var(--muted)", cardStatus: undefined };

  function rerun(e) {
    e.stopPropagation();
    navigate("/investigate", {
      state: { prefillNotes: item.alert_text, prefillDeploymentId: item.deployment_id ?? undefined },
    });
  }

  return (
    <Card
      status={meta.cardStatus}
      className="investigation-card"
      onClick={() => navigate(`/investigations/${item.id}`)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          navigate(`/investigations/${item.id}`);
        }
      }}
    >
      <div className="investigation-card-icon" style={{ color: meta.color }}>
        <Icon name={meta.icon} size={17} />
      </div>
      <div className="investigation-card-body">
        <div className="investigation-card-top">
          <span className="feed-source">{item.source}</span>
          {item.source_ref && <span className="feed-meta">{item.source_ref}</span>}
          {item.reviewed && (
            <span className="badge ok" style={{ marginLeft: 2 }}>
              reviewed
            </span>
          )}
        </div>
        <div className="investigation-card-alert">{truncate(item.alert_text, 100)}</div>
      </div>
      <div className="investigation-card-meta">
        <div className={"feed-status " + item.status}>{item.status}</div>
        <span className="feed-meta">{relativeTime(item.created_at)}</span>
      </div>
      <button type="button" className="row-action investigation-card-action" title="Re-run" onClick={rerun}>
        <Icon name="search" size={14} />
      </button>
    </Card>
  );
}
