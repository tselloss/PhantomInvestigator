import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Icon from "../components/Icon";
import CircularText from "../components/CircularText";
import PostmortemView from "../components/PostmortemView";
import { composeAlertText } from "../lib/composeAlertText";

export default function Investigate() {
  const [aiConfigured, setAiConfigured] = useState(true);
  const [tryingTo, setTryingTo] = useState("");
  const [instead, setInstead] = useState("");
  const [page, setPage] = useState("");
  const [notes, setNotes] = useState("");
  const [screenshotFile, setScreenshotFile] = useState(null);
  const [uploadingScreenshot, setUploadingScreenshot] = useState(false);
  const [screenshotNotice, setScreenshotNotice] = useState(null);
  const [running, setRunning] = useState(false);
  const [log, setLog] = useState([]);
  const [final, setFinal] = useState(null);
  const [deployments, setDeployments] = useState([]);
  const [deploymentId, setDeploymentId] = useState("");

  useEffect(() => {
    fetch("/api/clients/deployments")
      .then((r) => r.json())
      .then(setDeployments)
      .catch(() => {});
    fetch("/api/settings/ai")
      .then((r) => r.json())
      .then((data) => setAiConfigured(data.configured))
      .catch(() => {});
  }, []);

  async function start() {
    setRunning(true);
    setLog([]);
    setFinal(null);
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

    es.onmessage = (e) => {
      const event = JSON.parse(e.data);
      switch (event.type) {
        case "step_start":
          setLog((l) => [...l, { kind: "step", text: `Step ${event.step}` }]);
          break;
        case "tool_call":
          setLog((l) => [...l, { kind: "call", text: `→ ${event.name}(${JSON.stringify(event.input)})` }]);
          break;
        case "tool_result": {
          const text = event.result.length > 200 ? event.result.slice(0, 200) + "…" : event.result;
          setLog((l) => [...l, { kind: "out", text }]);
          break;
        }
        case "final":
          es.close();
          setFinal(event.data);
          setRunning(false);
          break;
      }
    };

    es.onerror = () => {
      es.close();
      setRunning(false);
      setFinal((f) => f ?? { result: "Stream error or connection closed." });
    };
  }

  const busy = running || uploadingScreenshot;

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
            disabled={busy}
            onChange={(e) => setScreenshotFile(e.target.files[0] || null)}
          />
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
        <button className="primary" disabled={busy || !aiConfigured} onClick={start}>
          <Icon name="search" size={14} />
          Investigate
        </button>
        {uploadingScreenshot && <span className="spinner">Analyzing screenshot…</span>}
      </div>

      {screenshotNotice && (
        <div className="alert warn">
          <Icon name="inbox" size={15} />
          <span>{screenshotNotice}</span>
        </div>
      )}

      <div style={{ marginTop: 16 }}>
        {running && log.length === 0 && (
          <div className="empty-state" style={{ border: "none" }}>
            <CircularText text="INVESTIGATING • GATHERING EVIDENCE • " spinDuration={9} onHover="pause">
              <Icon name="search" size={22} />
            </CircularText>
            <p style={{ marginTop: 18 }}>This can take 20–60s…</p>
          </div>
        )}

        {log.length > 0 && (
          <div className="stream-log">
            {log.map((line, i) => (
              <div key={i} className={line.kind}>
                {line.text}
              </div>
            ))}
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

        {final && final.postmortem && <PostmortemView pm={final.postmortem} />}
        {final && !final.postmortem && <pre>{final.result || JSON.stringify(final, null, 2)}</pre>}
      </div>
    </section>
  );
}
