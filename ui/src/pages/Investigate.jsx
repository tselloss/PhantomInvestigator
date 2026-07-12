import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import Icon from "../components/Icon";
import CircularText from "../components/CircularText";
import PostmortemView from "../components/PostmortemView";
import Button from "../components/Button";
import StatusDot from "../components/StatusDot";
import InvestigationTimeline from "../components/InvestigationTimeline";
import { eventToLogEntry } from "../lib/investigationLog";
import { composeAlertText } from "../lib/composeAlertText";
import { truncate, relativeTime } from "../lib/format";
import { integrationLabel } from "../lib/integrations";
import { useToast } from "../context/ToastContext";

function formatElapsed(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function Investigate() {
  const toast = useToast();
  const location = useLocation();
  const [aiConfigured, setAiConfigured] = useState(true);
  const [budget, setBudget] = useState(null);
  const [tryingTo, setTryingTo] = useState("");
  const [instead, setInstead] = useState("");
  const [page, setPage] = useState("");
  const [notes, setNotes] = useState("");
  const [screenshotFile, setScreenshotFile] = useState(null);
  const [uploadingScreenshot, setUploadingScreenshot] = useState(false);
  const [screenshotNotice, setScreenshotNotice] = useState(null);
  const [running, setRunning] = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [log, setLog] = useState([]);
  const [final, setFinal] = useState(null);
  const [deployments, setDeployments] = useState([]);
  const [deploymentId, setDeploymentId] = useState("");
  const [tickets, setTickets] = useState([]);
  const [ticketsLoading, setTicketsLoading] = useState(false);
  const [pickedTicketKey, setPickedTicketKey] = useState(null);
  const [stickBottom, setStickBottom] = useState(true);
  const esRef = useRef(null);
  const timerRef = useRef(null);
  const scrollRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (stickBottom && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [log, stickBottom]);

  useEffect(() => {
    fetch("/api/clients/deployments")
      .then((r) => r.json())
      .then(setDeployments)
      .catch(() => {});
    fetch("/api/settings/ai")
      .then((r) => r.json())
      .then((data) => setAiConfigured(data.configured))
      .catch(() => {});
    fetch("/api/settings/profile")
      .then((r) => r.json())
      .then(setBudget)
      .catch(() => {});
    // Don't leave a live stream/timer running past unmount (e.g. operator navigates away mid-run).
    return () => {
      clearInterval(timerRef.current);
      esRef.current?.close();
    };
  }, []);

  // Arriving from a Clients "Candidate incidents" row prefills the alert text (and
  // deployment, if the client has exactly one) so the operator doesn't retype it.
  useEffect(() => {
    if (location.state?.prefillNotes) setNotes(location.state.prefillNotes);
    if (location.state?.prefillDeploymentId) setDeploymentId(location.state.prefillDeploymentId);
  }, [location.state]);

  // Picking a deployment pulls in that client's still-open Jira/Azure DevOps/Zendesk
  // items directly -- so an operator can start from a real ticket instead of
  // retyping what someone already wrote there.
  useEffect(() => {
    setPickedTicketKey(null);
    if (!deploymentId) {
      setTickets([]);
      return;
    }
    const deployment = deployments.find((d) => String(d.id) === String(deploymentId));
    if (!deployment) {
      setTickets([]);
      return;
    }
    let cancelled = false;
    setTicketsLoading(true);
    fetch(`/api/clients/${deployment.client_id}/tickets`)
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled) setTickets(data);
      })
      .catch(() => {
        if (!cancelled) setTickets([]);
      })
      .finally(() => {
        if (!cancelled) setTicketsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [deploymentId, deployments]);

  function pickTicket(ticket) {
    setNotes(`${integrationLabel(ticket.source)} #${ticket.id}: ${ticket.title}`);
    setPickedTicketKey(`${ticket.source}-${ticket.id}`);
    toast.show("Ticket pulled in below — review and click Investigate.", { type: "ok" });
  }

  function handleScroll() {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setStickBottom(distanceFromBottom < 40);
  }

  function jumpToLatest() {
    setStickBottom(true);
  }

  function stopStreaming() {
    clearInterval(timerRef.current);
    esRef.current?.close();
    esRef.current = null;
  }

  function cancel() {
    stopStreaming();
    setRunning(false);
    toast.show("Investigation cancelled.", { type: "warn" });
  }

  async function start() {
    setRunning(true);
    setLog([]);
    setFinal(null);
    setElapsedSec(0);
    setStickBottom(true);
    setScreenshotNotice(null);

    let screenshotDescription = null;
    let screenshotId = null;

    if (screenshotFile) {
      setUploadingScreenshot(true);
      try {
        const data = new FormData();
        data.set("file", screenshotFile);
        if (deploymentId) data.set("deployment_id", deploymentId);
        const resp = await fetch("/api/investigate/screenshot", { method: "POST", body: data });
        if (!resp.ok) {
          const detail = await resp.json().catch(() => ({}));
          setUploadingScreenshot(false);
          setRunning(false);
          setScreenshotNotice(`Screenshot rejected: ${detail.detail || resp.statusText}`);
          return;
        }
        const body = await resp.json();
        screenshotId = body.id;
        if (body.vision_status === "ok") {
          screenshotDescription = body.vision_description;
        } else {
          setScreenshotNotice("Screenshot saved, but automated analysis failed — continuing with the text fields only.");
        }
      } catch {
        setUploadingScreenshot(false);
        setRunning(false);
        setScreenshotNotice("Screenshot upload failed — check your connection and try again.");
        return;
      } finally {
        setUploadingScreenshot(false);
      }
    }

    const alert = composeAlertText({ tryingTo, instead, page, notes, screenshotDescription });

    const params = new URLSearchParams({ alert });
    if (deploymentId) params.set("deployment_id", deploymentId);
    if (screenshotId) params.set("screenshot_id", screenshotId);
    const es = new EventSource(`/api/investigate/stream?${params}`);
    esRef.current = es;
    timerRef.current = setInterval(() => setElapsedSec((s) => s + 1), 1000);

    es.onmessage = (e) => {
      const event = JSON.parse(e.data);
      if (event.type === "final") {
        stopStreaming();
        setFinal(event.data);
        setRunning(false);
        return;
      }
      const entry = eventToLogEntry(event);
      if (entry) setLog((l) => [...l, { ...entry, at: Date.now() }]);
    };

    es.onerror = () => {
      stopStreaming();
      setRunning(false);
      setFinal((f) => f ?? { result: "Stream error or connection closed." });
      toast.show("The investigation stream disconnected unexpectedly.", { type: "err" });
    };
  }

  const busy = running || uploadingScreenshot;
  const budgetExceeded = budget?.monthly_limit_usd != null && budget.spent_this_month_usd >= budget.monthly_limit_usd;
  const submitted = running || log.length > 0 || final != null;
  const isErrorFinal = final != null && (final.partial === true || (!final.postmortem && !final.deduped && !final.investigation_id));

  const overallStatus = running ? "running" : !final ? null : isErrorFinal ? (final.partial ? "partial" : "error") : "done";
  const statusDotColor =
    overallStatus === "running" ? "phantom" : overallStatus === "done" ? "ok" : overallStatus === "partial" ? "warn" : "err";

  function editAgain() {
    if (running) stopStreaming();
    setRunning(false);
    setLog([]);
    setFinal(null);
  }

  const alertPreview = truncate(
    composeAlertText({ tryingTo, instead, page, notes, screenshotDescription: null })
      .replace(/\s+/g, " ")
      .trim(),
    90
  );

  return (
    <section>
      <h2>Investigate</h2>
      <p className="placeholder">
        Fill in whatever you know. A vague report is fine — attach a screenshot and we'll pull what we can out of it.
      </p>

      {!aiConfigured && (
        <div className="alert warn">
          <Icon name="zap" size={15} />
          <span>
            No AI provider key configured — add one in <Link to="/settings/integrations">Settings → Integrations</Link>{" "}
            before running an investigation.
          </span>
        </div>
      )}

      {budgetExceeded && (
        <div className="alert warn">
          <Icon name="dollar" size={15} />
          <span>
            Monthly AI spend cap of ${budget.monthly_limit_usd.toFixed(2)} reached (${budget.spent_this_month_usd.toFixed(2)}{" "}
            spent this month) — raise or remove it in <Link to="/settings/profile">Settings → Profile</Link> to keep
            investigating.
          </span>
        </div>
      )}

      {!submitted && (
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!busy && aiConfigured && !budgetExceeded) start();
        }}
      >
        <div className="row" style={{ marginTop: 14 }}>
          <div className="field grow">
            <label>Client / project</label>
            <select value={deploymentId} onChange={(e) => setDeploymentId(e.target.value)} disabled={busy}>
              <option value="">No deployment (demo/manual)</option>
              {deployments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.client_name} / {d.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {deploymentId && (
          <div className="ticket-picker">
            {ticketsLoading && (
              <div className="row" style={{ gap: 8, padding: "10px 2px" }}>
                <span className="mini-spinner" />
                <span className="feed-meta">Loading open tickets…</span>
              </div>
            )}
            {!ticketsLoading && tickets.length === 0 && (
              <p className="placeholder" style={{ margin: "8px 0 0", fontSize: 13 }}>
                No open tickets for this project — configure Jira, Azure DevOps, or Zendesk on{" "}
                <Link to="/clients">the Clients page</Link>, or just describe the incident below.
              </p>
            )}
            {!ticketsLoading && tickets.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
                {tickets.map((t) => {
                  const key = `${t.source}-${t.id}`;
                  return (
                    <div className={"feed-row ticket-row" + (pickedTicketKey === key ? " picked" : "")} key={key}>
                      <div className="row" style={{ gap: 8 }}>
                        <span className="feed-source">{integrationLabel(t.source)}</span>
                        <span className="feed-meta">#{t.id}</span>
                        {t.url ? (
                          <a href={t.url} target="_blank" rel="noreferrer">
                            {t.title}
                          </a>
                        ) : (
                          <span>{t.title}</span>
                        )}
                        {t.type && <span className="tag">{t.type}</span>}
                      </div>
                      <div className="row" style={{ gap: 8 }}>
                        <span className="feed-meta">{t.status}</span>
                        <span className="feed-meta">{relativeTime(t.updated)}</span>
                        <Button
                          type="button"
                          variant={pickedTicketKey === key ? "primary" : undefined}
                          icon={pickedTicketKey === key ? "check" : "search"}
                          disabled={busy}
                          onClick={() => pickTicket(t)}
                        >
                          {pickedTicketKey === key ? "Pulled in" : "Use this"}
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        <div className="row" style={{ marginTop: 14 }}>
          <div className="field">
            <label>What were they trying to do?</label>
            <input
              type="text"
              value={tryingTo}
              onChange={(e) => setTryingTo(e.target.value)}
              placeholder="Optional"
              disabled={busy}
            />
          </div>
          <div className="field">
            <label>What happened instead?</label>
            <input
              type="text"
              value={instead}
              onChange={(e) => setInstead(e.target.value)}
              placeholder="Optional"
              disabled={busy}
            />
          </div>
          <div className="field">
            <label>Page or feature</label>
            <input
              type="text"
              value={page}
              onChange={(e) => setPage(e.target.value)}
              placeholder="Optional"
              disabled={busy}
            />
          </div>
        </div>

        <div className="row" style={{ marginTop: 14 }}>
          <div className="field grow">
            <label>Alert text or ticket reference</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Alert text, or a Jira ticket key/summary"
              disabled={busy}
            />
          </div>
          <div className="field">
            <label>Screenshot</label>
            <input
              type="file"
              accept="image/*"
              ref={fileInputRef}
              style={{ display: "none" }}
              onChange={(e) => setScreenshotFile(e.target.files[0] || null)}
            />
            <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
              <button
                type="button"
                style={{ flex: 1, minWidth: 0 }}
                disabled={busy}
                onClick={() => fileInputRef.current?.click()}
              >
                <Icon name="image" size={14} />
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {screenshotFile ? truncate(screenshotFile.name, 24) : "Attach screenshot"}
                </span>
              </button>
              {screenshotFile && (
                <button
                  type="button"
                  className="ghost"
                  disabled={busy}
                  title="Remove screenshot"
                  onClick={() => {
                    setScreenshotFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = "";
                  }}
                >
                  <Icon name="x" size={14} />
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="row" style={{ marginTop: 16 }}>
          <button className="primary" type="submit" disabled={busy || !aiConfigured || budgetExceeded}>
            <Icon name="search" size={14} />
            Investigate
          </button>
          {uploadingScreenshot && <span className="spinner">Analyzing screenshot…</span>}
        </div>
      </form>
      )}

      {screenshotNotice && (
        <div className="alert warn">
          <Icon name="inbox" size={15} />
          <span>{screenshotNotice}</span>
        </div>
      )}

      <div style={{ marginTop: 16 }}>
        {submitted && (
          <div className="investigate-summary-bar">
            <div className="investigate-summary-title">
              <StatusDot status={statusDotColor} live={running} />
              <span>{alertPreview}</span>
            </div>
            <div className="investigate-summary-meta">
              <span className="investigate-elapsed">{formatElapsed(elapsedSec)}</span>
              {running ? (
                <Button variant="ghost" icon="x" onClick={cancel}>
                  Cancel
                </Button>
              ) : (
                <Button variant="ghost" onClick={editAgain}>
                  Edit
                </Button>
              )}
            </div>
          </div>
        )}

        {running && log.length === 0 && (
          <div className="empty-state" style={{ border: "none" }}>
            <CircularText text="INVESTIGATING • GATHERING EVIDENCE • " spinDuration={9} onHover="pause">
              <Icon name="search" size={22} />
            </CircularText>
            <p style={{ marginTop: 18 }}>This can take 20–60s…</p>
          </div>
        )}

        {log.length > 0 && (
          <div className="timeline-scroll" ref={scrollRef} onScroll={handleScroll}>
            <InvestigationTimeline log={log} running={running} />
            {!stickBottom && (
              <div className="jump-to-latest-wrap">
                <button type="button" className="jump-to-latest" onClick={jumpToLatest}>
                  <Icon name="chevron" size={12} style={{ transform: "rotate(90deg)" }} />
                  Jump to latest
                </button>
              </div>
            )}
          </div>
        )}

        {!running && !final && log.length === 0 && (
          <div className="empty-state">
            <Icon name="search" size={28} />
            <p>Enter what you know, or attach a screenshot, then click Investigate.</p>
          </div>
        )}

        {final && isErrorFinal && (
          <div className="alert err" style={{ marginTop: 0, marginBottom: 12 }}>
            <Icon name="x" size={15} />
            <div style={{ flex: 1 }}>
              <div>{final.result || "The investigation didn't finish cleanly."}</div>
              <div className="row" style={{ gap: 8, marginTop: 10 }}>
                <Button variant="primary" icon="search" onClick={start}>
                  Retry investigation
                </Button>
                {final.investigation_id && (
                  <Link to={`/investigations/${final.investigation_id}`}>
                    <Button variant="ghost">View partial result</Button>
                  </Link>
                )}
              </div>
            </div>
          </div>
        )}

        {final && !isErrorFinal && final.deduped && (
          <div className="alert ok" style={{ marginTop: 0, marginBottom: 12 }}>
            <Icon name="check" size={15} />
            <span>
              Same alert was already investigated recently — reused{" "}
              <Link to={`/investigations/${final.investigation_id}`}>that result</Link> instead of spending AI tokens
              on a repeat run.
            </span>
          </div>
        )}

        {final && !isErrorFinal && !final.deduped && final.investigation_id && (
          <div className="row" style={{ justifyContent: "flex-end", marginBottom: 10 }}>
            <Link to={`/investigations/${final.investigation_id}`}>
              <button type="button" className="ghost">
                View in history
                <Icon name="arrowLeft" size={13} className="flip" />
              </button>
            </Link>
          </div>
        )}

        {final && !isErrorFinal && final.postmortem && <PostmortemView pm={final.postmortem} />}
        {final && !isErrorFinal && !final.postmortem && !final.deduped && (
          <pre>{final.result || JSON.stringify(final, null, 2)}</pre>
        )}
      </div>
    </section>
  );
}
