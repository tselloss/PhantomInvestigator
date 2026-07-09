import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Icon from "../components/Icon";
import PostmortemView from "../components/PostmortemView";

const FEEDBACK_LABELS = { correct: "Correct", partial: "Partially correct", incorrect: "Incorrect" };
const FEEDBACK_BADGE_CLASS = { correct: "ok", partial: "warn", incorrect: "err" };

export default function InvestigationDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [item, setItem] = useState(null);
  const [error, setError] = useState(null);
  const [rerunning, setRerunning] = useState(false);
  const [deployments, setDeployments] = useState([]);
  const [resolvingPost, setResolvingPost] = useState(false);
  const [editingFeedback, setEditingFeedback] = useState(false);
  const [feedbackNotes, setFeedbackNotes] = useState("");
  const [savingFeedback, setSavingFeedback] = useState(false);

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

  async function resolvePendingPost(action) {
    setResolvingPost(true);
    try {
      const res = await fetch(`/api/investigations/${id}/${action}`, { method: "POST" });
      if (res.ok) setItem(await res.json());
    } finally {
      setResolvingPost(false);
    }
  }

  async function submitFeedback(rating) {
    setSavingFeedback(true);
    try {
      const res = await fetch(`/api/investigations/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reviewed: true, feedback_rating: rating, feedback_notes: feedbackNotes || null }),
      });
      if (res.ok) {
        setItem(await res.json());
        setEditingFeedback(false);
      }
    } finally {
      setSavingFeedback(false);
    }
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
          {item.feedback_rating && (
            <span className={"badge " + FEEDBACK_BADGE_CLASS[item.feedback_rating]}>
              {FEEDBACK_LABELS[item.feedback_rating]}
            </span>
          )}
          <span className="feed-meta">{new Date(item.created_at).toLocaleString()}</span>
        </div>

        {item.status === "awaiting_approval" && item.pending_action?.type === "jira_comment" && (
          <div className="alert warn" style={{ flexDirection: "column", alignItems: "stretch", gap: 10 }}>
            <div className="row" style={{ gap: 6 }}>
              <Icon name="inbox" size={15} />
              <span>Ready to post to Jira ticket {item.pending_action.key} — review before sending:</span>
            </div>
            <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{item.pending_action.body}</pre>
            <div className="row">
              <button className="primary" disabled={resolvingPost} onClick={() => resolvePendingPost("approve-post")}>
                <Icon name="check" size={14} />
                {resolvingPost ? "Posting…" : "Post to Jira"}
              </button>
              <button disabled={resolvingPost} onClick={() => resolvePendingPost("dismiss-post")}>
                <Icon name="x" size={14} />
                Discard
              </button>
            </div>
          </div>
        )}

        {pm ? <PostmortemView pm={pm} /> : <pre>{item.result?.result || "No structured postmortem for this run."}</pre>}

        <div className="panel" style={{ marginTop: 16 }}>
          <h3 style={{ marginTop: 0 }}>Feedback</h3>
          {item.feedback_rating && !editingFeedback ? (
            <div>
              <p style={{ margin: "0 0 8px" }}>
                Marked <strong>{FEEDBACK_LABELS[item.feedback_rating]}</strong>
                {item.feedback_notes ? `: ${item.feedback_notes}` : "."}
              </p>
              <button
                onClick={() => {
                  setFeedbackNotes(item.feedback_notes || "");
                  setEditingFeedback(true);
                }}
              >
                Edit feedback
              </button>
            </div>
          ) : (
            <div>
              <p style={{ margin: "0 0 8px", color: "var(--muted)" }}>
                Was this postmortem right? Feedback here is exported via <code>make export-feedback</code> to improve
                prompts and eval fixtures.
              </p>
              <textarea
                placeholder="Optional notes — what was right or wrong?"
                value={feedbackNotes}
                onChange={(e) => setFeedbackNotes(e.target.value)}
                rows={2}
                style={{ width: "100%", marginBottom: 8 }}
              />
              <div className="row">
                <button disabled={savingFeedback} onClick={() => submitFeedback("correct")}>
                  <Icon name="check" size={14} />
                  Correct
                </button>
                <button disabled={savingFeedback} onClick={() => submitFeedback("partial")}>
                  Partially correct
                </button>
                <button disabled={savingFeedback} onClick={() => submitFeedback("incorrect")}>
                  <Icon name="x" size={14} />
                  Incorrect
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
