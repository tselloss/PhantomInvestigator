import { Link } from "react-router-dom";
import { relativeTime, truncate } from "../lib/format";

export default function FeedRow({ item, deploymentLabel, index = 0 }) {
  return (
    <Link className="feed-row" to={`/investigations/${item.id}`} style={{ animationDelay: `${Math.min(index, 10) * 30}ms` }}>
      <div>
        <span className="feed-source">{item.source}</span>
        {item.source_ref ? ` ${item.source_ref}` : ""}
        {deploymentLabel && (
          <span className="feed-meta" style={{ marginLeft: 6, marginRight: 6 }}>
            · {deploymentLabel}
          </span>
        )}
        {" — "}
        {truncate(item.alert_text, 80)}
        {item.reviewed && (
          <span className="badge ok" style={{ marginLeft: 8 }}>
            reviewed
          </span>
        )}
      </div>
      <div className="row" style={{ gap: 10, flexShrink: 0 }}>
        <span className="feed-meta">{relativeTime(item.created_at)}</span>
        <div className={"feed-status " + item.status}>{item.status}</div>
      </div>
    </Link>
  );
}
