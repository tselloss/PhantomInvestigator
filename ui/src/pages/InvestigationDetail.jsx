import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Icon from "../components/Icon";
import PostmortemView from "../components/PostmortemView";

export default function InvestigationDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [item, setItem] = useState(null);
  const [error, setError] = useState(null);
  const [rerunning, setRerunning] = useState(false);
  const [deployments, setDeployments] = useState([]);

  async function load() {
    try {
      const res = await fetch(`/api/investigations/${id}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setItem(await res.json());
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  useEffect(() => {
    fetch("/api/clients/deployments?include_archived=true")
      .then((r) => r.json())
      .then(setDeployments)
      .catch(() => {});
  }, []);

  const deployment = item?.deployment_id != null ? deployments.find((d) => d.id === item.deployment_id) : null;

  async function toggleReviewed() {
    const next = !item.reviewed;
    setItem((i) => ({ ...i, reviewed: next }));
    await fetch(`/api/investigations/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewed: next }),
    });
  }

  async function rerun() {
    setRerunning(true);
    try {
      await fetch("/api/investigate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alert: item.alert_text, deployment_id: item.deployment_id }),
      });
      navigate("/investigations");
    } finally {
      setRerunning(false);
    }
  }

  if (error) return <div className="alert err">Couldn't load investigation: {error}</div>;
  if (!item) {
    return (
      <section>
        <div className="skeleton" style={{ width: 160, height: 16, marginBottom: 18 }} />
        <div className="skeleton" style={{ width: "70%", height: 12, marginBottom: 10 }} />
        <div className="skeleton" style={{ width: "40%", height: 12, marginBottom: 22 }} />
        <div className="skeleton" style={{ width: "100%", height: 80 }} />
      </section>
    );
  }

  const pm = item.result?.postmortem;
  const sourceLink =
    item.source === "jira" && item.source_ref
      ? { href: "#", label: `Jira ${item.source_ref}` } // Jira base URL isn't exposed to the frontend; label only.
      : item.source === "github" && item.source_ref
      ? { href: "#", label: `GitHub run ${item.source_ref}` }
      : null;

  return (
    <section>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <Link to="/investigations" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 500 }}>
          <Icon name="arrowLeft" size={14} />
          Back to investigations
        </Link>
        <div className="row">
          <button onClick={toggleReviewed}>
            <Icon name="check" size={14} />
            {item.reviewed ? "Mark unreviewed" : "Mark reviewed"}
          </button>
          <button className="primary" disabled={rerunning} onClick={rerun}>
            {rerunning ? "Starting…" : "Re-run"}
          </button>
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <div className="row" style={{ marginBottom: 16 }}>
          <span className="tag accent">{item.source}</span>
          <span className={"badge " + (item.status === "done" ? "ok" : item.status === "error" ? "err" : "warn")}>
            {item.status}
          </span>
          {sourceLink && <span className="tag">{sourceLink.label}</span>}
          {deployment && <span className="tag">{deployment.client_name} / {deployment.label}</span>}
          {item.reviewed && <span className="badge ok">reviewed</span>}
          <span className="feed-meta">{new Date(item.created_at).toLocaleString()}</span>
        </div>

        {pm ? <PostmortemView pm={pm} /> : <pre>{item.result?.result || "No structured postmortem for this run."}</pre>}
      </div>
    </section>
  );
}
