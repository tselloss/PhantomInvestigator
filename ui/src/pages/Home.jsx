import { useEffect, useRef, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import Icon from "../components/Icon";
import Threads from "../components/Threads";
import MagicBento from "../components/MagicBento";
import { useAuth } from "../context/AuthContext";

const FEATURES = [
  {
    id: "investigate",
    icon: "search",
    label: "Core",
    title: "Autonomous investigation",
    description:
      "Describe an incident, or let a webhook trigger one automatically. The agent gathers logs, metrics, deployments, and tickets on its own, then returns a complete postmortem.",
    wide: true,
  },
  {
    id: "integrates",
    icon: "zap",
    title: "Integrates with your stack",
    description: "Prometheus, Loki, Jira, GitHub Actions, Azure Monitor, and AWS CloudWatch.",
  },
  {
    id: "byok",
    icon: "dollar",
    title: "Bring your own AI provider",
    description: "Usage is billed directly to your own provider account, never ours.",
  },
];

const KINETIC_WORDS = ["Jira tickets", "failed CI runs", "Prometheus spikes", "Slack alerts", "on-call pages"];

const DEMO_SCRIPT = [
  { kind: "step", text: "Step 1" },
  { kind: "call", text: 'jira_get_issue({"key":"OPS-482"})' },
  { kind: "out", text: 'Checkout 500s on payment submit — priority High, since 14:02 UTC' },
  { kind: "call", text: 'github_list_deploys({"repo":"acme/storefront"})' },
  { kind: "out", text: "a91f2c3 at 13:58 UTC — \"bump payment-sdk to 4.2.0\"" },
  { kind: "step", text: "Step 2" },
  { kind: "call", text: 'prometheus_query({"query":"rate(http_requests_total{status=\\"500\\"}[5m])"})' },
  { kind: "out", text: "Error rate 0.02/s → 4.8/s, starts 14:02:11 — correlates with deploy a91f2c3" },
  { kind: "done", text: "Root cause: payment-sdk 4.2.0 regression. Postmortem ready." },
];

function useReducedMotion() {
  const [reduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  return reduced;
}

function LiveDemoMock() {
  const reduced = useReducedMotion();
  const [count, setCount] = useState(reduced ? DEMO_SCRIPT.length : 0);
  const logRef = useRef(null);

  useEffect(() => {
    if (reduced) return;
    const id = setInterval(() => {
      setCount((c) => (c >= DEMO_SCRIPT.length ? 0 : c + 1));
    }, 850);
    return () => clearInterval(id);
  }, [reduced]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [count]);

  const lines = DEMO_SCRIPT.slice(0, count);

  return (
    <div className="hero-demo">
      <div className="hero-demo-titlebar">
        <span className="hero-demo-dot err" />
        <span className="hero-demo-dot warn" />
        <span className="hero-demo-dot ok" />
        <span className="hero-demo-label">investigate --live</span>
      </div>
      <div className="stream-log hero-demo-log" ref={logRef}>
        {lines.map((line, i) =>
          line.kind === "done" ? (
            <div key={i} className="alert ok hero-demo-done">
              <Icon name="check" size={14} />
              <span>{line.text}</span>
            </div>
          ) : (
            <div key={i} className={line.kind}>
              {line.text}
            </div>
          )
        )}
        {count < DEMO_SCRIPT.length && <span className="hero-demo-cursor" />}
      </div>
    </div>
  );
}

export default function Home() {
  const { user } = useAuth();
  const reduced = useReducedMotion();
  const [wordIndex, setWordIndex] = useState(0);

  useEffect(() => {
    if (reduced) return;
    const id = setInterval(() => setWordIndex((i) => (i + 1) % KINETIC_WORDS.length), 2400);
    return () => clearInterval(id);
  }, [reduced]);

  if (user) return <Navigate to="/dashboard" replace />;

  return (
    <div className="landing" style={{ maxWidth: "min(1600px, 96vw)", margin: "0 auto" }}>
      <div className="landing-ambient" aria-hidden="true">
        <Threads color={[91, 140, 255]} amplitude={0.7} distance={0.12} />
      </div>
      <span className="landing-glow landing-glow-a" aria-hidden="true" />
      <span className="landing-glow landing-glow-b" aria-hidden="true" />

      <div className="hero hero-grain">
        <div className="hero-grid">
          <div className="hero-copy">
            <div className="row" style={{ alignItems: "center", gap: 12, marginBottom: 4 }}>
              <span className="brand-mark hero-mark" style={{ width: 56, height: 56 }}>
                <Icon name="ghost" size={30} />
              </span>
              <span className="brand-shine" style={{ fontSize: 20, fontWeight: 700 }}>
                Phantom Investigator
              </span>
            </div>
            <h1>
              Your AI SRE for{" "}
              <span key={wordIndex} className="kinetic-word">
                {KINETIC_WORDS[wordIndex]}
              </span>
            </h1>
            <p>
              An autonomous agent that investigates production incidents on your behalf — reads the ticket, checks
              the deploy diff, queries your metrics and logs, and posts a structured root-cause postmortem back.
            </p>

            <div className="row" style={{ marginTop: 26 }}>
              <Link to="/register" className="primary" style={{ display: "inline-flex" }}>
                <Icon name="arrowLeft" size={14} className="flip" />
                Create account
              </Link>
              <Link to="/login" style={{ display: "inline-flex", alignItems: "center" }}>
                Sign in
              </Link>
            </div>
            <div className="row" style={{ marginTop: 14, gap: 8 }}>
              <span className="tag">Self-hosted</span>
              <span className="tag">Private by design</span>
              <span className="tag">Bring your own key</span>
            </div>
          </div>

          <div className="hero-demo-stage">
            <LiveDemoMock />
          </div>
        </div>
      </div>

      <section>
        <h2>Why Phantom Investigator</h2>
        <MagicBento items={FEATURES} enableStars textAutoHide={false} />
      </section>

      <div className="landing-footer">
        <p className="placeholder">
          Self-hosted and fully private — no other account can see your clients, investigations, or credentials.
          Create an account and add your own AI provider key to get started.
        </p>
        <div className="row landing-footer-links" style={{ justifyContent: "center", gap: 16 }}>
          <Link to="/docs">Documentation</Link>
          <a href="https://github.com/tselloss" target="_blank" rel="noopener noreferrer">
            GitHub
          </a>
          <a href="https://buymeacoffee.com/tsellosskr" target="_blank" rel="noopener noreferrer">
            Support the project
          </a>
        </div>
      </div>
    </div>
  );
}
