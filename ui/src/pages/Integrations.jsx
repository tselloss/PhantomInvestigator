import { useEffect, useState } from "react";

export default function Integrations() {
  const [integrations, setIntegrations] = useState([]);
  const [testing, setTesting] = useState(null);
  const [results, setResults] = useState({});

  async function load() {
    const res = await fetch("/api/settings/integrations");
    setIntegrations(await res.json());
  }

  useEffect(() => {
    load();
  }, []);

  async function test(name) {
    setTesting(name);
    try {
      const res = await fetch(`/api/settings/integrations/${name}/test`, { method: "POST" });
      const data = await res.json();
      setResults((r) => ({ ...r, [name]: data }));
    } finally {
      setTesting(null);
    }
  }

  return (
    <section>
      <h2>Integrations</h2>
      <p className="placeholder">
        Configured via .env — this page never displays credential values, only presence and live connection status.
      </p>

      {integrations.map((i) => (
        <div className="feed-row" key={i.name}>
          <div>
            <span className="feed-source">{i.name}</span>
            {" — "}
            <span className={i.configured ? "" : "placeholder"}>{i.configured ? "configured" : "not configured"}</span>
            {results[i.name] && (
              <span style={{ marginLeft: 10, color: results[i.name].ok ? "var(--ok)" : "var(--err)" }}>
                {results[i.name].detail}
              </span>
            )}
          </div>
          <button disabled={!i.configured || testing === i.name} onClick={() => test(i.name)}>
            {testing === i.name ? "Testing…" : "Test connection"}
          </button>
        </div>
      ))}
    </section>
  );
}
