import { useEffect, useState } from "react";
import StatusDot from "./StatusDot";

export default function StatusPill() {
  const [text, setText] = useState("checking...");
  const [faulted, setFaulted] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function refresh() {
      try {
        const res = await fetch("/api/demo/health");
        const data = await res.json();
        const faults = data.active_faults || [];
        if (cancelled) return;
        if (faults.length) {
          setText("active: " + faults.join(", "));
          setFaulted(true);
        } else {
          setText("healthy");
          setFaulted(false);
        }
      } catch {
        if (!cancelled) {
          setText("demo-app unreachable");
          setFaulted(true);
        }
      }
    }
    refresh();
    const id = setInterval(refresh, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <span className={"status-pill" + (faulted ? " faulted" : "")}>
      <StatusDot status={faulted ? "warn" : "ok"} live={!faulted} />
      {text}
    </span>
  );
}
