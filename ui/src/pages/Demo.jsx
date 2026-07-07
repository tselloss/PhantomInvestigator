import { useEffect, useState } from "react";

const FAULTS = ["slow_db", "bad_deploy", "memory_leak", "error_spike"];

export default function Demo() {
  const [busy, setBusy] = useState(null);
  const [evalResult, setEvalResult] = useState(null);
  const [evalRunning, setEvalRunning] = useState(false);
  const [evalError, setEvalError] = useState(null);

  async function loadLatestEval() {
    try {
      const res = await fetch("/api/evals/latest");
      const data = await res.json();
      setEvalResult(data.available ? data : null);
    } catch {
      // best-effort; leave whatever was there
    }
  }

  useEffect(() => {
    loadLatestEval();
  }, []);

  async function inject(fault) {
    setBusy(fault);
    try {
      await fetch(`/api/demo/faults/${fault}`, { method: "POST" });
    } finally {
      setBusy(null);
    }
  }

  async function clear() {
    setBusy("clear");
    try {
      await fetch("/api/demo/faults", { method: "DELETE" });
    } finally {
      setBusy(null);
    }
  }

  async function runEvals() {
    setEvalRunning(true);
    setEvalError(null);
    try {
      await fetch("/api/evals/run", { method: "POST" });
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
        <h2>Inject a fault (demo-shop)</h2>
        <div className="fault-grid">
          {FAULTS.map((f) => (
            <button key={f} disabled={busy === f} onClick={() => inject(f)}>
              {f}
            </button>
          ))}
        </div>
        <div className="row" style={{ marginTop: 10 }}>
          <button className="danger" disabled={busy === "clear"} onClick={clear}>
            Clear faults
          </button>
        </div>
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
        {evalError && <p style={{ color: "var(--err)" }}>{evalError}</p>}
        {evalResult && (
          <div style={{ marginTop: 12 }}>
            <p className="pm-meta">Latest run: {evalResult.filename}</p>
            <pre>{JSON.stringify(evalResult.summary, null, 2)}</pre>
          </div>
        )}
      </section>
    </>
  );
}
