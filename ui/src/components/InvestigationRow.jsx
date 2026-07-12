import { useNavigate } from "react-router-dom";
import Icon from "./Icon";
import { relativeTime, truncate } from "../lib/format";

export default function InvestigationRow({ item, deploymentLabel, showDeployment, onMarkReviewed }) {
  const navigate = useNavigate();

  function rerun(e) {
    e.stopPropagation();
    navigate("/investigate", {
      state: { prefillNotes: item.alert_text, prefillDeploymentId: item.deployment_id ?? undefined },
    });
  }

  function markReviewed(e) {
    e.stopPropagation();
    onMarkReviewed?.(item.id);
  }

  return (
    <tr className="inv-row" onClick={() => navigate(`/investigations/${item.id}`)}>
      <td className={"inv-td-status-bar status-" + item.status} aria-hidden="true" />
      <td className="inv-td-source">
        <span className="feed-source">{item.source}</span>
        {item.source_ref ? ` ${item.source_ref}` : ""}
      </td>
      <td className="inv-td-alert">
        {truncate(item.alert_text, 90)}
        {item.reviewed && (
          <span className="badge ok" style={{ marginLeft: 8 }}>
            reviewed
          </span>
        )}
      </td>
      {showDeployment && <td className="inv-td-deployment">{deploymentLabel || "—"}</td>}
      <td className="inv-td-statuscol">
        <div className={"feed-status " + item.status}>{item.status}</div>
      </td>
      <td className="inv-td-time" title={new Date(item.created_at).toLocaleString()}>
        {relativeTime(item.created_at)}
      </td>
      <td className="inv-td-actions">
        <button type="button" className="row-action" title="Re-run" onClick={rerun}>
          <Icon name="search" size={14} />
        </button>
        {!item.reviewed && onMarkReviewed && (
          <button type="button" className="row-action" title="Mark reviewed" onClick={markReviewed}>
            <Icon name="check" size={14} />
          </button>
        )}
      </td>
    </tr>
  );
}
