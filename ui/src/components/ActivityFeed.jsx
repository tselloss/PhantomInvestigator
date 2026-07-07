import { useEffect, useState } from "react";

export default function ActivityFeed({ refreshKey }) {
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch("/investigations?limit=20");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) setItems(data);
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    }
    load();
    const id = setInterval(load, 10000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [refreshKey]);

  return (
    <section>
      <h2>Webhook activity</h2>
      {error && <p className="placeholder">Couldn't load activity: {error}</p>}
      {!error && items.length === 0 && (
        <p className="placeholder">No webhook-triggered investigations yet.</p>
      )}
      {items.map((it) => (
        <div className="feed-row" key={it.id}>
          <div>
            <span className="feed-source">{it.source}</span>
            {it.source_ref ? ` ${it.source_ref}` : ""}
            {" — "}
            {it.alert_text.length > 80 ? it.alert_text.slice(0, 80) + "…" : it.alert_text}
          </div>
          <div className={"feed-status " + it.status}>{it.status}</div>
        </div>
      ))}
    </section>
  );
}
