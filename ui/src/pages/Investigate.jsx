import { useState } from "react";
import PostmortemView from "../components/PostmortemView";

export default function Investigate() {
  const [alertText, setAlertText] = useState("Manual investigation triggered from UI.");
  const [running, setRunning] = useState(false);
  const [log, setLog] = useState([]);
  const [final, setFinal] = useState(null);

  function start() {
    setRunning(true);
    setLog([]);
    setFinal(null);

    const es = new EventSource(`/api/investigate/stream?alert=${encodeURIComponent(alertText)}`);

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

  return (
    <section>
      <h2>Investigate</h2>
      <div className="row">
        <input
          type="text"
          value={alertText}
          onChange={(e) => setAlertText(e.target.value)}
          placeholder="Alert text, or a Jira ticket key/summary"
          disabled={running}
        />
        <button className="primary" disabled={running} onClick={start}>
          Investigate
        </button>
        {running && <span className="spinner">Investigating… this can take 20–60s</span>}
      </div>

      <div style={{ marginTop: 16 }}>
        {log.length > 0 && (
          <div className="stream-log">
            {log.map((line, i) => (
              <div key={i} className={line.kind}>
                {line.text}
              </div>
            ))}
          </div>
        )}

        {!final && log.length === 0 && <p className="placeholder">Enter an alert or ticket, then click Investigate.</p>}

        {final && final.postmortem && <PostmortemView pm={final.postmortem} />}
        {final && !final.postmortem && <pre>{final.result || JSON.stringify(final, null, 2)}</pre>}
      </div>
    </section>
  );
}
