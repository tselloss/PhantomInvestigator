import { Link, Navigate } from "react-router-dom";
import Icon from "../components/Icon";
import { useAuth } from "../context/AuthContext";

const FEATURES = [
  {
    icon: "search",
    title: "Autonomous investigation",
    body: "Describe an incident or let a webhook trigger one — the agent pulls logs, metrics, deploys, and tickets on its own and comes back with a postmortem.",
  },
  {
    icon: "zap",
    title: "Plugs into what you already run",
    body: "Prometheus, Loki, Jira, GitHub Actions, Azure Monitor, AWS CloudWatch — connect the ones you use from Settings, skip the rest.",
  },
  {
    icon: "dollar",
    title: "Free tool, your own AI credits",
    body: "Phantom Investigator itself is free to self-host. You bring your own Claude, OpenAI, or compatible API key — your usage is billed to your account, never ours.",
  },
];

export default function Home() {
  const { user } = useAuth();

  if (user) return <Navigate to="/dashboard" replace />;

  return (
    <main style={{ maxWidth: 860, margin: "0 auto", padding: "0 28px" }}>
      <section className="hero">
        <span className="brand-mark" style={{ width: 52, height: 52, fontSize: 26, margin: "0 auto 18px" }}>
          👻
        </span>
        <h1>Phantom Investigator</h1>
        <p>
          An AI agent that investigates incidents for you — free and open to self-host. Connect your own
          Claude or OpenAI key and it's your credits doing the work, not ours.
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
      </section>

      <div className="feature-grid">
        {FEATURES.map((f) => (
          <div className="feature-card" key={f.title}>
            <Icon name={f.icon} size={20} />
            <h3>{f.title}</h3>
            <p>{f.body}</p>
          </div>
        ))}
      </div>

      <p className="placeholder" style={{ textAlign: "center", margin: "8px 0 16px" }}>
        Self-hosted, and every account is fully private — nobody else can see your clients, investigations, or
        credentials. Just create an account and add your own AI provider key.
      </p>

      <div className="row" style={{ justifyContent: "center", gap: 16, margin: "0 0 40px" }}>
        <a href="https://github.com/tselloss" target="_blank" rel="noopener noreferrer">
          GitHub
        </a>
        <a href="https://buymeacoffee.com/tsellosskr" target="_blank" rel="noopener noreferrer">
          ☕ Buy me a coffee
        </a>
      </div>
    </main>
  );
}
