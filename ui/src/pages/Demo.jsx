import { useEffect, useState } from "react";
import { useToast } from "../context/ToastContext";

const FAULTS = ["slow_db", "bad_deploy", "memory_leak", "error_spike"];
const MOCKED_INTEGRATIONS = ["Jira", "GitHub", "Azure DevOps", "Azure Monitor", "AWS CloudWatch", "Zendesk"];

export default function Demo() {
  const toast = useToast();
  const [busy, setBusy] = useState(null);
  const [evalResult, setEvalResult] = useState(null);
  const [evalRunning, setEvalRunning] = useState(false);
  const [evalError, setEvalError] = useState(null);
  const [demoMode, setDemoMode] = useState(null);
  const [demoModeSaving, setDemoModeSaving] = useState(false);
  const [activeFaults, setActiveFaults] = useState([]);
  const [leakedCacheMb, setLeakedCacheMb] = useState(0);
  const [appHealthy, setAppHealthy] = useState(null);
  const [traffic, setTraffic] = useState([]);
  const [trafficRunning, setTrafficRunning] = useState(false);

  async function loadLatestEval() {
    try {
      const res = await fetch("/api/evals/latest");
      const data = await res.json();
      setEvalResult(data.available ? data : null);
    } catch {
      // best-effort; leave whatever was there
    }
  }

  async function loadDemoAppHealth() {
    try {
      const res = await fetch("/api/demo/health");
      if (!res.ok) throw new Error("unreachable");
      const data = await res.json();
      setActiveFaults(data.active_faults || []);
      setLeakedCacheMb(data.leaked_cache_mb || 0);
      setAppHealthy(true);
    } catch {
      setAppHealthy(false);
    }
  }

  async function loadProfile() {
    try {
      const res = await fetch("/api/settings/profile");
      if (!res.ok) throw new Error("load failed");
      const data = await res.json();
      setDemoMode(Boolean(data.demo_mode));
    } catch {
      // best-effort; the toggle just won't render its current state
    }
  }

  useEffect(() => {
    loadLatestEval();
    loadProfile();
    loadDemoAppHealth();
    const poll = setInterval(loadDemoAppHealth, 4000);
    return () => clearInterval(poll);
  }, []);

  async function toggleDemoMode() {
    const next = !demoMode;
    setDemoModeSaving(true);
    try {
      const res = await fetch("/api/settings/profile/demo-mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: next }),
      });
      if (!res.ok) {
        toast.show(`Couldn't update demo mode (HTTP ${res.status})`, { type: "err" });
        return;
      }
      setDemoMode(next);
    } catch {
      toast.show("Couldn't update demo mode — check your connection.", { type: "err" });
    } finally {
      setDemoModeSaving(false);
    }
  }

  async function inject(fault) {
    setBusy(fault);
    try {
      const res = await fetch(`/api/demo/faults/${fault}`, { method: "POST" });
      if (!res.ok) toast.show(`Couldn't inject fault (HTTP ${res.status})`, { type: "err" });
    } catch {
      toast.show("Couldn't inject fault — check your connection.", { type: "err" });
    } finally {
      setBusy(null);
      loadDemoAppHealth();
    }
  }

  async function clear() {
    setBusy("clear");
    try {
      const res = await fetch("/api/demo/faults", { method: "DELETE" });
      if (!res.ok) toast.show(`Couldn't clear faults (HTTP ${res.status})`, { type: "err" });
    } catch {
      toast.show("Couldn't clear faults — check your connection.", { type: "err" });
    } finally {
      setBusy(null);
      setTraffic([]);
      loadDemoAppHealth();
    }
  }

  async function sendTraffic() {
    setTrafficRunning(true);
    try {
      const res = await fetch("/api/demo/checkout-test?count=5", { method: "POST" });
      if (!res.ok) {
        toast.show(`Couldn't send test traffic (HTTP ${res.status})`, { type: "err" });
        return;
      }
      const data = await res.json();
      setTraffic(data.results || []);
    } catch {
      toast.show("Couldn't send test traffic — check your connection.", { type: "err" });
    } finally {
      setTrafficRunning(false);
    }
  }

  async function runEvals() {
    setEvalRunning(true);
    setEvalError(null);
    try {
      const res = await fetch("/api/evals/run", { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        setEvalError(detail.detail || `HTTP ${res.status}`);
        setEvalRunning(false);
        return;
      }
    } catch (e) {
      setEvalError(e.message);
      setEvalRunning(false);
      return;
    }
    // Eval run takes several minutes (real LLM calls across all faults) --
    // poll for the new results file rather than blocking the request.
    const poll = setInterval(async () => {
      await loadLatestEval();
    }, 15000);
    setTimeout(() => {
      clearInterval(poll);
      setEvalRunning(false);
    }, 10 * 60 * 1000);
  }

  return (
    <>
      <section>
        <h2>Demo mode for real-source tools</h2>
        <p className="placeholder">
          {MOCKED_INTEGRATIONS.join(", ")} normally need real credentials to return anything. With demo mode on,
          any of those that isn't actually configured falls back to a realistic canned response instead of an
          error — so an investigation can show the full tool belt in action with zero real accounts connected.
          Configured integrations are never affected; real credentials always win.
        </p>
        <div className="feed-row">
          <div className="row" style={{ gap: 8 }}>
            <span>{demoMode ? "Demo mode is on" : "Demo mode is off"}</span>
            {demoMode != null && <span className={`badge ${demoMode ? "ok" : ""}`}>{demoMode ? "mocking unconfigured tools" : "real tools only"}</span>}
          </div>
          <button
            className={demoMode ? "danger" : "primary"}
            disabled={demoMode == null || demoModeSaving}
            onClick={toggleDemoMode}
          >
            {demoModeSaving ? "Saving…" : demoMode ? "Turn off" : "Turn on"}
          </button>
        </div>
      </section>

      <section>
        <h2>Inject a fault (demo-shop)</h2>
        <div className="feed-row">
          <div className="row" style={{ gap: 8 }}>
            {appHealthy === false && <span className="badge err">demo-app unreachable</span>}
            {appHealthy !== false && activeFaults.length === 0 && <span className="badge ok">no faults active</span>}
            {appHealthy !== false && activeFaults.length > 0 && (
              <>
                <span>Active:</span>
                {activeFaults.map((f) => (
                  <span key={f} className="badge err">{f}</span>
                ))}
              </>
            )}
            {leakedCacheMb > 0 && (
              <span className="badge warn" title="memory_leak has no effect on status code or latency — this counter is its only visible signal, and it keeps growing even after Clear faults, same as a real unbounded cache would.">
                leaked cache: {leakedCacheMb} MB
              </span>
            )}
          </div>
        </div>
        <div className="fault-grid" style={{ marginTop: 10 }}>
          {FAULTS.map((f) => {
            const isActive = activeFaults.includes(f);
            return (
              <button key={f} className={isActive ? "danger" : ""} disabled={busy === f} onClick={() => inject(f)}>
                {isActive ? `● ${f}` : f}
              </button>
            );
          })}
        </div>
        <div className="row" style={{ marginTop: 10, gap: 8 }}>
          <button className="danger" disabled={busy === "clear"} onClick={clear}>
            Clear faults
          </button>
          <button className="primary" disabled={trafficRunning || appHealthy === false} onClick={sendTraffic}>
            {trafficRunning ? "Sending…" : "Send test traffic (5 requests)"}
          </button>
        </div>

        {traffic.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <p className="pm-meta">
              Live /checkout results — see the fault's effect directly. (memory_leak doesn't affect status/latency;
              watch the "leaked cache" badge above instead.)
            </p>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              {traffic.map((r, i) => (
                <span
                  key={i}
                  className={`badge ${r.status_code && r.status_code < 400 ? "ok" : "err"}`}
                  title={r.error || ""}
                >
                  {r.status_code ?? "ERR"} · {r.latency_ms}ms
                </span>
              ))}
            </div>
          </div>
        )}
      </section>

      <section>
        <h2>Eval harness</h2>
        <p className="placeholder">
          Runs the full fault matrix against real Anthropic API calls (several minutes, real cost) --
          see docs/decisions.md before running repeatedly.
        </p>
        <div className="row">
          <button className="primary" disabled={evalRunning} onClick={runEvals}>
            {evalRunning ? "Running…" : "Run evals"}
          </button>
        </div>
        {evalError && <div className="alert err">{evalError}</div>}
        {evalResult && (
          <div style={{ marginTop: 12 }}>
            <p className="pm-meta">
              Latest run: <span className="tag">{evalResult.filename}</span>
            </p>
            <pre>{JSON.stringify(evalResult.summary, null, 2)}</pre>
          </div>
        )}
      </section>
    </>
  );
}
