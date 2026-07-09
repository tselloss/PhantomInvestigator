import { Link, Navigate } from "react-router-dom";
import Icon from "../components/Icon";
import Threads from "../components/Threads";
import { useAuth } from "../context/AuthContext";

const FEATURES = [
  {
    icon: "search",
    title: "Autonomous investigation",
    body: "Describe an incident, or let a webhook trigger one automatically. The agent gathers logs, metrics, deployments, and tickets on its own, then returns a complete postmortem.",
  },
  {
    icon: "zap",
    title: "Integrates with your stack",
    body: "Prometheus, Loki, Jira, GitHub Actions, Azure Monitor, and AWS CloudWatch. Connect the integrations you use from Settings and skip the rest.",
  },
  {
    icon: "dollar",
    title: "Bring your own AI provider",
    body: "Phantom Investigator is free and open-source to self-host. Connect your own Claude, OpenAI, or compatible API key — usage is billed directly to your account, never ours.",
  },
];

export default function Home() {
  const { user } = useAuth();

  if (user) return <Navigate to="/dashboard" replace />;

  return (
    <div className="landing" style={{ maxWidth: 860, margin: "0 auto" }}>
      <div className="hero" style={{ position: "relative", overflow: "hidden" }}>
        <div style={{ position: "absolute", inset: "-40% -20%", zIndex: 0, opacity: 0.55 }}>
          <Threads color={[91, 140, 255]} amplitude={0.9} distance={0.15} enableMouseInteraction />
        </div>
        <div style={{ position: "relative", zIndex: 1 }}>
          <span className="brand-mark hero-mark" style={{ width: 56, height: 56, fontSize: 28, margin: "0 auto 20px" }}>
            👻
          </span>
          <h1>Phantom Investigator</h1>
          <p>
            An autonomous AI agent that investigates production incidents on your behalf. Free and open-source
            to self-host — connect your own Claude or OpenAI key, and usage is billed directly to your account,
            never ours.
          </p>
          <div className="row" style={{ justifyContent: "center" }}>
            <Link to="/register" className="primary" style={{ display: "inline-flex" }}>
              <Icon name="arrowLeft" size={14} className="flip" />
              Create account
            </Link>
            <Link to="/login" style={{ display: "inline-flex", alignItems: "center" }}>
              Sign in
            </Link>
          </div>
        </div>
      </div>

      <div className="feature-grid">
        {FEATURES.map((f) => (
          <div className="feature-card" key={f.title}>
            <div className="feature-icon">
              <Icon name={f.icon} size={19} />
            </div>
            <h3>{f.title}</h3>
            <p>{f.body}</p>
          </div>
        ))}
      </div>

      <div className="landing-footer">
        <p className="placeholder">
          Self-hosted and fully private — no other account can see your clients, investigations, or credentials.
          Create an account and add your own AI provider key to get started.
        </p>
        <div className="row landing-footer-links" style={{ justifyContent: "center", gap: 16 }}>
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
