import { useState } from "react";

const FAULTS = ["slow_db", "bad_deploy", "memory_leak", "error_spike"];

export default function FaultPanel({ onChange }) {
  const [busy, setBusy] = useState(null);

  async function inject(fault) {
    setBusy(fault);
    try {
      await fetch(`/demo/faults/${fault}`, { method: "POST" });
    } finally {
      setBusy(null);
      onChange?.();
    }
  }

  async function clear() {
    setBusy("clear");
    try {
      await fetch("/demo/faults", { method: "DELETE" });
    } finally {
      setBusy(null);
      onChange?.();
    }
  }

  return (
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
  );
}
