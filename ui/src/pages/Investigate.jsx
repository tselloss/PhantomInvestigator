import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import Icon from "../components/Icon";
import CircularText from "../components/CircularText";
import PostmortemView from "../components/PostmortemView";
import { composeAlertText } from "../lib/composeAlertText";
import { truncate } from "../lib/format";
import { useToast } from "../context/ToastContext";

export default function Investigate() {
  const toast = useToast();
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
  const [streaming, setStreaming] = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [log, setLog] = useState([]);
  const [final, setFinal] = useState(null);
  const [deployments, setDeployments] = useState([]);
  const [deploymentId, setDeploymentId] = useState("");
  const esRef = useRef(null);
  const timerRef = useRef(null);
  const logRef = useRef(null);
  const fileInputRef = useRef(null);
  const stepCount = log.filter((l) => l.kind === "step").length;

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [log]);

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

  function stopStreaming() {
    clearInterval(timerRef.current);
    esRef.current?.close();
    esRef.current = null;
    setStreaming(false);
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
    setStreaming(true);
    timerRef.current = setInterval(() => setElapsedSec((s) => s + 1), 1000);

    es.onmessage = (e) => {
      const event = JSON.parse(e.data);
      switch (event.type) {
        case "step_start":
          setLog((l) => [...l, { kind: "step", step: event.step }]);
          break;
        case "tool_call":
          setLog((l) => [...l, { kind: "call", name: event.name, input: event.input }]);
          break;
        case "tool_result": {
          const text = event.result.length > 200 ? event.result.slice(0, 200) + "…" : event.result;
          setLog((l) => [...l, { kind: "out", text }]);
          break;
        }
        case "final":
          stopStreaming();
          setFinal(event.data);
          setRunning(false);
          break;
      }
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

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!busy && aiConfigured && !budgetExceeded) start();
        }}
      >
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
          <div className="field">
            <label>Deployment</label>
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

        <div className="row" style={{ marginTop: 16 }}>
          <button className="primary" type="submit" disabled={busy || !aiConfigured || budgetExceeded}>
            <Icon name="search" size={14} />
            Investigate
          </button>
          {uploadingScreenshot && <span className="spinner">Analyzing screenshot…</span>}
        </div>
      </form>

      {screenshotNotice && (
        <div className="alert warn">
          <Icon name="inbox" size={15} />
          <span>{screenshotNotice}</span>
        </div>
      )}

      <div style={{ marginTop: 16 }}>
        {streaming && (
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
            <span className="feed-meta">
              {stepCount > 0 ? `Step ${stepCount} · ` : "Starting… · "}
              {elapsedSec}s elapsed
            </span>
            <button type="button" className="ghost" onClick={cancel}>
              <Icon name="x" size={13} />
              Cancel
            </button>
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
          <div className="stream-log" ref={logRef}>
            {log.map((line, i) => {
              if (line.kind === "step") {
                return (
                  <div key={i} className="step">
                    Step {line.step}
                  </div>
                );
              }
              if (line.kind === "call") {
                return (
                  <div key={i} className="call">
                    {line.name}({JSON.stringify(line.input)})
                  </div>
                );
              }
              const preview = truncate(line.text.replace(/\s+/g, " ").trim(), 70);
              return (
                <details key={i} className="out">
                  <summary>{preview || "(empty result)"}</summary>
                  <div className="out-body">{line.text}</div>
                </details>
              );
            })}
          </div>
        )}

        {!running && !final && log.length === 0 && (
          <div className="empty-state">
            <Icon name="search" size={28} />
            <p>Enter what you know, or attach a screenshot, then click Investigate.</p>
          </div>
        )}

        {final && final.deduped && (
          <div className="alert ok" style={{ marginTop: 0, marginBottom: 12 }}>
            <Icon name="check" size={15} />
            <span>
              Same alert was already investigated recently — reused{" "}
              <Link to={`/investigations/${final.investigation_id}`}>that result</Link> instead of spending AI tokens
              on a repeat run.
            </span>
          </div>
        )}

        {final && !final.deduped && final.investigation_id && (
          <div className="row" style={{ justifyContent: "flex-end", marginBottom: 10 }}>
            <Link to={`/investigations/${final.investigation_id}`}>
              <button type="button" className="ghost">
                View in history
                <Icon name="arrowLeft" size={13} className="flip" />
              </button>
            </Link>
          </div>
        )}

        {final && final.postmortem && <PostmortemView pm={final.postmortem} />}
        {final && !final.postmortem && <pre>{final.result || JSON.stringify(final, null, 2)}</pre>}
      </div>
    </section>
  );
}
