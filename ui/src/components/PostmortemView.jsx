export default function PostmortemView({ pm }) {
  const confidencePct = Math.round((pm.confidence ?? 0) * 100);
  const confidenceLevel = confidencePct >= 75 ? "ok" : confidencePct >= 45 ? "warn" : "err";

  return (
    <div className="pm-view">
      <div className="pm-header">
        <div>
          <span className="pm-category">{pm.fault_category || "unknown"}</span>
          <h2 className="pm-title">{pm.title || "Untitled incident"}</h2>
        </div>
        <div className={"pm-confidence " + confidenceLevel}>
          <div className="pm-confidence-value">{confidencePct}%</div>
          <div className="pm-confidence-label">confidence</div>
        </div>
      </div>
      <div className="pm-section">
        <h3>Root cause</h3>
        <p>{pm.root_cause}</p>
      </div>
      {pm.timeline?.length > 0 && (
        <div className="pm-section timeline">
          <h3>Timeline</h3>
          <ul>
            {pm.timeline.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </div>
      )}
      {pm.evidence?.length > 0 && (
        <div className="pm-section">
          <h3>Evidence</h3>
          {pm.evidence.map((e, i) => (
            <div className="evidence-item" key={i}>
              <div className="evidence-source">{e.source}</div>
              <div>{e.detail}</div>
            </div>
          ))}
        </div>
      )}
      <div className="pm-section">
        <h3>Suggested fix</h3>
        <p>{pm.suggested_fix}</p>
      </div>
      {pm.contributing_factors?.length > 0 && (
        <div className="pm-section">
          <h3>Contributing factors</h3>
          {pm.contributing_factors.map((f, i) => (
            <div className="evidence-item" key={i}>
              <div className="evidence-source">{f.fault_category}</div>
              <div>{f.description}</div>
            </div>
          ))}
        </div>
      )}
      {pm.similar_past_incidents?.length > 0 && (
        <div className="pm-section">
          <h3>Similar past incidents</h3>
          <ul>
            {pm.similar_past_incidents.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
