import { Link } from "react-router-dom";
import Icon from "../components/Icon";

const SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "getting-started", label: "Getting started" },
  { id: "clients", label: "Clients & deployments" },
  { id: "integrations", label: "Integrations" },
  { id: "investigating", label: "Running an investigation" },
  { id: "postmortems", label: "Postmortems & approval" },
  { id: "runbooks", label: "Runbooks" },
  { id: "settings", label: "Settings" },
];

export default function Docs() {
  return (
    <div className="auth-page" style={{ maxWidth: 820, margin: "0 auto", padding: "40px 20px 70px" }}>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 24 }}>
        <Link to="/" className="row" style={{ gap: 8, alignItems: "center" }}>
          <span className="brand-mark" style={{ width: 28, height: 28 }}>
            <Icon name="ghost" size={16} />
          </span>
          <strong>Phantom Investigator</strong>
        </Link>
        <div className="row" style={{ gap: 14 }}>
          <Link to="/login">Sign in</Link>
          <Link to="/register">Create account</Link>
        </div>
      </div>

      <div style={{ textAlign: "center", marginBottom: 28 }}>
        <span className="brand-mark hero-mark" style={{ width: 44, height: 44, margin: "0 auto 12px" }}>
          <Icon name="book" size={22} />
        </span>
        <h2 className="brand-shine" style={{ margin: "0 0 4px", fontSize: 19, fontWeight: 700 }}>
          Documentation
        </h2>
        <p className="placeholder" style={{ margin: 0, fontSize: 13 }}>
          How Phantom Investigator works and how to use it.
        </p>
      </div>

      <nav aria-label="Sections" style={{ marginBottom: 32 }}>
        <div className="row" style={{ flexWrap: "wrap", gap: 8, justifyContent: "center" }}>
          {SECTIONS.map((s) => (
            <a key={s.id} href={`#${s.id}`} className="tag">
              {s.label}
            </a>
          ))}
        </div>
      </nav>

      <section style={{ display: "flex", flexDirection: "column", gap: 30, fontSize: 14, lineHeight: 1.65 }}>
        <div id="overview">
          <h3 style={{ fontSize: 16, marginBottom: 6 }}>Overview</h3>
          <p style={{ margin: 0 }}>
            Phantom Investigator is an AI agent that debugs production incidents like an SRE. Point it at a Jira
            ticket, an Azure DevOps work item, or a failed CI run — or let a webhook trigger it automatically — and
            it checks the deploy diff, queries your metrics and logs, searches a runbook knowledge base, and returns
            a structured root-cause postmortem. Nothing is posted back to a ticket without an operator approving it
            first.
          </p>
        </div>

        <div id="getting-started">
          <h3 style={{ fontSize: 16, marginBottom: 6 }}>Getting started</h3>
          <p style={{ margin: 0 }}>
            Create an account, then add your own AI provider key (Claude, OpenAI, or a compatible provider) from{" "}
            <strong>Settings → Profile</strong>. Usage is billed directly to your provider account — Phantom
            Investigator itself is free to run. Once a key is configured, add a client and a deployment (see below)
            and you're ready to trigger your first investigation.
          </p>
        </div>

        <div id="clients">
          <h3 style={{ fontSize: 16, marginBottom: 6 }}>Clients & deployments</h3>
          <p style={{ margin: 0 }}>
            A <strong>client</strong> represents a team or product you support; each client can have multiple{" "}
            <strong>deployments</strong> (e.g. production, staging), configured with a label, environment, and links
            to its Jira project, GitHub repo, or Azure DevOps project. Deployments keep investigations, candidate
            incidents, and integration credentials scoped separately, so results for one client never leak into
            another's.
          </p>
        </div>

        <div id="integrations">
          <h3 style={{ fontSize: 16, marginBottom: 6 }}>Integrations</h3>
          <p style={{ margin: 0, marginBottom: 10 }}>
            Connect the systems the agent should pull context from: <strong>Jira</strong>, <strong>Azure DevOps</strong>,
            and <strong>Zendesk</strong> for tickets; <strong>GitHub Actions</strong> and <strong>Azure DevOps</strong>{" "}
            for deploys and CI logs; <strong>Prometheus</strong>, <strong>Loki</strong>, <strong>Azure Monitor</strong>,
            and <strong>AWS CloudWatch</strong> for metrics and logs. Configure a shared default under{" "}
            <strong>Settings → Integrations</strong>, or override any of them per-client on that client's page —
            a per-client credential always takes priority over the shared default. Use "Test connection" after
            saving to confirm credentials work before relying on them.
          </p>
        </div>

        <div id="investigating">
          <h3 style={{ fontSize: 16, marginBottom: 6 }}>Running an investigation</h3>
          <p style={{ margin: 0 }}>
            From <strong>Investigate</strong>, describe what happened — what you were trying to do, what happened
            instead, which page or area, and any notes — optionally attach a screenshot and pick the affected
            deployment. If the deployment has open tickets, you can pull one in directly instead of retyping it.
            Investigations can also start automatically from a Jira/Azure DevOps webhook or a failed GitHub Actions
            run. Once started, the agent's tool calls and reasoning stream live so you can follow along in real
            time, ending in a postmortem (or a partial result if it couldn't reach a conclusion).
          </p>
        </div>

        <div id="postmortems">
          <h3 style={{ fontSize: 16, marginBottom: 6 }}>Postmortems & approval</h3>
          <p style={{ margin: 0 }}>
            Every completed investigation produces a structured postmortem: root cause, supporting evidence, and a
            suggested fix. Posting that postmortem back to the originating ticket always requires an operator to
            review and explicitly approve it first — the agent never comments on Jira, Azure DevOps, or Zendesk
            without that human-in-the-loop step.
          </p>
        </div>

        <div id="runbooks">
          <h3 style={{ fontSize: 16, marginBottom: 6 }}>Runbooks</h3>
          <p style={{ margin: 0 }}>
            Runbooks are markdown files describing known incident patterns (e.g. bad deploys, memory leaks,
            connection pool exhaustion). They're chunked, embedded, and retrieved as context during an
            investigation, so the agent can recognize incident types your team has documented before.
            Re-ingest from the <strong>Runbooks</strong> tab after editing or adding a file — unchanged content is
            skipped automatically.
          </p>
        </div>

        <div id="settings">
          <h3 style={{ fontSize: 16, marginBottom: 6 }}>Settings</h3>
          <p style={{ margin: 0 }}>
            <strong>Profile</strong> holds your AI provider key and an optional monthly spend cap in dollars —
            once the cap is hit, new investigations are blocked until the next calendar month or the cap is
            raised. <strong>Integrations</strong> holds the shared default credentials used by any client that
            doesn't have its own override.
          </p>
        </div>
      </section>

      <p className="placeholder" style={{ textAlign: "center", fontSize: 13, marginTop: 32 }}>
        <Link to="/">Back to home</Link>
      </p>
    </div>
  );
}
