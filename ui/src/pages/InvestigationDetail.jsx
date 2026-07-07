import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import PostmortemView from "../components/PostmortemView";

export default function InvestigationDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [item, setItem] = useState(null);
  const [error, setError] = useState(null);
  const [rerunning, setRerunning] = useState(false);

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
        body: JSON.stringify({ alert: item.alert_text }),
      });
      navigate("/investigations");
    } finally {
      setRerunning(false);
    }
  }

  if (error) return <p className="placeholder">Couldn't load investigation: {error}</p>;
  if (!item) return <p className="placeholder">Loading…</p>;

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
        <Link to="/investigations">← Back to investigations</Link>
        <div className="row">
          <button onClick={toggleReviewed}>{item.reviewed ? "Mark unreviewed" : "Mark reviewed"}</button>
          <button className="primary" disabled={rerunning} onClick={rerun}>
            {rerunning ? "Starting…" : "Re-run"}
          </button>
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <p className="pm-meta">
          <span className="feed-source">{item.source}</span>
          {sourceLink && ` · ${sourceLink.label}`} · {item.status} · {new Date(item.created_at).toLocaleString()}
        </p>

        {pm ? <PostmortemView pm={pm} /> : <pre>{item.result?.result || "No structured postmortem for this run."}</pre>}
      </div>
    </section>
  );
}
