import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Icon from "../components/Icon";
import Button from "../components/Button";
import Card from "../components/Card";
import Skeleton from "../components/Skeleton";
import DiffView from "../components/DiffView";
import InvestigationTimeline from "../components/InvestigationTimeline";
import PostmortemView from "../components/PostmortemView";
import { eventToLogEntry } from "../lib/investigationLog";
import { useToast } from "../context/ToastContext";

const FEEDBACK_LABELS = { correct: "Correct", partial: "Partially correct", incorrect: "Incorrect" };
const FEEDBACK_BADGE_CLASS = { correct: "ok", partial: "warn", incorrect: "err" };

function postmortemToMarkdown(pm, item) {
  const lines = [
    `# ${pm.title || "Untitled incident"}`,
    "",
    `- **Category:** ${pm.fault_category || "unknown"}`,
    `- **Confidence:** ${Math.round((pm.confidence ?? 0) * 100)}%`,
    `- **Source:** ${item.source}${item.source_ref ? " " + item.source_ref : ""}`,
    `- **Investigated:** ${new Date(item.created_at).toLocaleString()}`,
    "",
    "## Root cause",
    pm.root_cause || "",
  ];
  if (pm.timeline?.length) {
    lines.push("", "## Timeline", ...pm.timeline.map((t) => `- ${t}`));
  }
  if (pm.evidence?.length) {
    lines.push("", "## Evidence", ...pm.evidence.map((e) => `- **${e.source}:** ${e.detail}`));
  }
  lines.push("", "## Suggested fix", pm.suggested_fix || "");
  if (pm.contributing_factors?.length) {
    lines.push("", "## Contributing factors", ...pm.contributing_factors.map((f) => `- **${f.fault_category}:** ${f.description}`));
  }
  return lines.join("\n");
}

function downloadFile(filename, content, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function InvestigationDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [item, setItem] = useState(null);
  const [error, setError] = useState(null);
  const [rerunning, setRerunning] = useState(false);
  const [deployments, setDeployments] = useState([]);
  const [resolvingPost, setResolvingPost] = useState(false);
  const [resolvingFix, setResolvingFix] = useState(false);
  const [selectedBranch, setSelectedBranch] = useState(null);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    fetch("/api/clients/deployments?include_archived=true")
      .then((r) => r.json())
      .then(setDeployments)
      .catch(() => {});
  }, []);

  const deployment = item?.deployment_id != null ? deployments.find((d) => d.id === item.deployment_id) : null;
  const pm = item?.result?.postmortem;
  const timelineLog = useMemo(() => (item?.trace || []).map(eventToLogEntry).filter(Boolean), [item?.trace]);

  async function resolvePendingPost(action) {
    setResolvingPost(true);
    try {
      const res = await fetch(`/api/investigations/${id}/${action}`, { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        toast.show(detail.detail || `That didn't go through (HTTP ${res.status}).`, { type: "err" });
        return;
      }
      const pendingType = item?.pending_action?.type;
      setItem(await res.json());
      if (action !== "approve-post") {
        toast.show("Discarded.", { type: "ok" });
      } else {
        toast.show(pendingType === "azure_devops_comment" ? "Posted to Azure DevOps." : "Posted to Jira.", { type: "ok" });
      }
    } catch {
      toast.show("Couldn't reach the server — check your connection.", { type: "err" });
    } finally {
      setResolvingPost(false);
    }
  }

  async function resolvePendingFix(action) {
    setResolvingFix(true);
    try {
      const res = await fetch(`/api/investigations/${id}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(action === "approve-fix" ? { target_branch: selectedBranch } : {}),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        toast.show(detail.detail || `That didn't go through (HTTP ${res.status}).`, { type: "err" });
        return;
      }
      const body = await res.json();
      setItem(body);
      setSelectedBranch(null);
      toast.show(action === "approve-fix" ? "Pull request opened." : "Discarded.", { type: "ok" });
    } catch {
      toast.show("Couldn't reach the server — check your connection.", { type: "err" });
    } finally {
      setResolvingFix(false);
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
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        toast.show(detail.detail || `Couldn't save feedback (HTTP ${res.status}).`, { type: "err" });
        return;
      }
      setItem(await res.json());
      setEditingFeedback(false);
      toast.show("Feedback saved.", { type: "ok" });
    } catch {
      toast.show("Couldn't save feedback — check your connection.", { type: "err" });
    } finally {
      setSavingFeedback(false);
    }
  }

  async function rerun() {
    setRerunning(true);
    try {
      const res = await fetch("/api/investigate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alert: item.alert_text, deployment_id: item.deployment_id }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        toast.show(detail.detail || `Couldn't start a re-run (HTTP ${res.status}).`, { type: "err" });
        return;
      }
      const body = await res.json();
      toast.show("Re-run started.", { type: "ok" });
      navigate(`/investigations/${body.investigation_id}`);
    } catch {
      toast.show("Couldn't start a re-run — check your connection.", { type: "err" });
    } finally {
      setRerunning(false);
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      toast.show("Link copied.", { type: "ok" });
    } catch {
      toast.show("Couldn't copy the link — your browser blocked clipboard access.", { type: "err" });
    }
  }

  function exportPostmortem() {
    if (pm) {
      downloadFile(`investigation-${item.id}.md`, postmortemToMarkdown(pm, item), "text/markdown");
    } else {
      downloadFile(`investigation-${item.id}.json`, JSON.stringify(item, null, 2), "application/json");
    }
  }

  if (error) return <div className="alert err">Couldn't load investigation: {error}</div>;
  if (!item) {
    return (
      <section>
        <Skeleton width={160} height={16} style={{ marginBottom: 18 }} />
        <Skeleton width="70%" height={12} style={{ marginBottom: 10 }} />
        <Skeleton width="40%" height={12} style={{ marginBottom: 22 }} />
        <Skeleton height={80} />
      </section>
    );
  }

  const sourceLink =
    item.source === "jira" && item.source_ref && item.jira_url
      ? { href: item.jira_url, label: `Jira ${item.source_ref}` }
      : item.source === "github" && item.source_ref && deployment?.github_repo
      ? { href: `https://github.com/${deployment.github_repo}/actions/runs/${item.source_ref}`, label: `GitHub run ${item.source_ref}` }
      : item.source === "jira" && item.source_ref
      ? { href: null, label: `Jira ${item.source_ref}` }
      : item.source === "github" && item.source_ref
      ? { href: null, label: `GitHub run ${item.source_ref}` }
      : null;

  return (
    <section>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <Link to="/investigations" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 500 }}>
          <Icon name="arrowLeft" size={14} />
          Back to investigations
        </Link>
        <div className="row">
          <Button variant="ghost" icon="link" onClick={copyLink}>
            Copy link
          </Button>
          <Button variant="ghost" icon="download" onClick={exportPostmortem}>
            Export
          </Button>
          <Button variant="primary" loading={rerunning} onClick={rerun}>
            {rerunning ? "Starting…" : "Re-run"}
          </Button>
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <div className="row" style={{ marginBottom: 16 }}>
          <span className="tag accent">{item.source}</span>
          <span className={"badge " + (item.status === "done" ? "ok" : item.status === "error" ? "err" : "warn")}>
            {item.status}
          </span>
          {sourceLink && sourceLink.href && (
            <a className="tag" href={sourceLink.href} target="_blank" rel="noopener noreferrer">
              {sourceLink.label}
              <Icon name="arrowLeft" size={11} style={{ transform: "rotate(135deg)" }} />
            </a>
          )}
          {sourceLink && !sourceLink.href && <span className="tag">{sourceLink.label}</span>}
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
              <Button variant="primary" icon="check" loading={resolvingPost} onClick={() => resolvePendingPost("approve-post")}>
                {resolvingPost ? "Posting…" : "Post to Jira"}
              </Button>
              <Button icon="x" disabled={resolvingPost} onClick={() => resolvePendingPost("dismiss-post")}>
                Discard
              </Button>
            </div>
          </div>
        )}

        {item.status === "awaiting_approval" && item.pending_action?.type === "azure_devops_comment" && (
          <div className="alert warn" style={{ flexDirection: "column", alignItems: "stretch", gap: 10 }}>
            <div className="row" style={{ gap: 6 }}>
              <Icon name="inbox" size={15} />
              <span>Ready to post to Azure DevOps work item {item.pending_action.work_item_id} — review before sending:</span>
            </div>
            <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{item.pending_action.body}</pre>
            <div className="row">
              <Button variant="primary" icon="check" loading={resolvingPost} onClick={() => resolvePendingPost("approve-post")}>
                {resolvingPost ? "Posting…" : "Post to Azure DevOps"}
              </Button>
              <Button icon="x" disabled={resolvingPost} onClick={() => resolvePendingPost("dismiss-post")}>
                Discard
              </Button>
            </div>
          </div>
        )}

        {item.status === "awaiting_approval" && item.pending_fix_action && (
          <div className="alert warn" style={{ flexDirection: "column", alignItems: "stretch", gap: 10 }}>
            <div className="row" style={{ gap: 6 }}>
              <Icon name="inbox" size={15} />
              <span>
                Ready to open a pull request on <strong>{item.pending_fix_action.repo}</strong> — review the diff
                before pushing:
              </span>
            </div>
            {item.pending_fix_action.files.map((f) => (
              <DiffView key={f.path} path={f.path} diff={f.diff} />
            ))}
            <div className="row">
              {item.pending_fix_action.allowed_base_branches.length > 1 ? (
                <div className="field" style={{ minWidth: 160, flex: "none" }}>
                  <label>Target branch</label>
                  <select
                    value={selectedBranch ?? item.pending_fix_action.default_branch}
                    onChange={(e) => setSelectedBranch(e.target.value)}
                  >
                    {item.pending_fix_action.allowed_base_branches.map((b) => (
                      <option key={b} value={b}>
                        {b}
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <span className="tag">{item.pending_fix_action.default_branch}</span>
              )}
            </div>
            <div className="row">
              <Button variant="primary" icon="check" loading={resolvingFix} onClick={() => resolvePendingFix("approve-fix")}>
                {resolvingFix ? "Opening…" : "Open pull request"}
              </Button>
              <Button icon="x" disabled={resolvingFix} onClick={() => resolvePendingFix("dismiss-fix")}>
                Discard
              </Button>
            </div>
          </div>
        )}

        {pm ? <PostmortemView pm={pm} /> : <pre>{item.result?.result || "No structured postmortem for this run."}</pre>}

        {timelineLog.length > 0 && (
          <Card style={{ marginTop: 16 }}>
            <h3 style={{ marginTop: 0, marginBottom: 14 }}>Timeline</h3>
            <InvestigationTimeline log={timelineLog} running={false} />
          </Card>
        )}

        <Card style={{ marginTop: 16 }}>
          <h3 style={{ marginTop: 0 }}>Feedback</h3>
          {item.feedback_rating && !editingFeedback ? (
            <div>
              <p style={{ margin: "0 0 8px" }}>
                Marked <strong>{FEEDBACK_LABELS[item.feedback_rating]}</strong>
                {item.feedback_notes ? `: ${item.feedback_notes}` : "."}
              </p>
              <Button
                onClick={() => {
                  setFeedbackNotes(item.feedback_notes || "");
                  setEditingFeedback(true);
                }}
              >
                Edit feedback
              </Button>
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
                <Button disabled={savingFeedback} icon="check" onClick={() => submitFeedback("correct")}>
                  Correct
                </Button>
                <Button disabled={savingFeedback} onClick={() => submitFeedback("partial")}>
                  Partially correct
                </Button>
                <Button disabled={savingFeedback} icon="x" onClick={() => submitFeedback("incorrect")}>
                  Incorrect
                </Button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </section>
  );
}
