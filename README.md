# 👻 Phantom Investigator

[![Buy Me A Coffee](https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png)](https://buymeacoffee.com/tsellosskr)

> An AI agent that debugs production incidents like an SRE: reads the Jira ticket, checks recent CI/deploy history, queries metrics and logs, cross-references past postmortems (RAG), and writes a root-cause report — every step traced.

Built on the same agent architecture as [AIInvestigator](https://github.com/tselloss/AIInvestigator) (its demo-app/Prometheus/Loki proving ground for the agent loop, kept here for regression testing), extended to investigate **real** production incidents sourced from Jira and GitHub Actions — triggered automatically via webhooks, with results posted back to the ticket.

## How it works

1. A Jira ticket gets created/labeled, or a GitHub Actions workflow run fails.
2. A webhook fires (`/webhooks/jira` or `/webhooks/github`), which kicks off an investigation in the background.
3. The agent runs autonomously: reads the triggering ticket or workflow run, checks recent deploy diffs (real GitHub compare API), queries metrics/logs, and searches a runbook knowledge base (hybrid vector + full-text RAG).
4. It returns a structured root-cause postmortem — title, root cause, confidence, timeline, cited evidence, suggested fix, similar past incidents.
5. The postmortem is posted back as a Jira comment, and every step (each LLM call, each tool call) is traced in Langfuse.

The demo-app + Prometheus/Loki/Grafana stack from AIInvestigator stays in place — useful for exercising the agent loop against synthetic faults without needing live prod access.

## Architecture

```
┌──────────┐  webhook   ┌─────────────────────────────────┐
│   Jira   │───────────▶│         AGENT (FastAPI)          │
└──────────┘            │  ┌─────────────────────────────┐ │
┌──────────┐  webhook   │  │  operator UI (React, :8085)  │ │
│  GitHub  │───────────▶│  └──────────────┬──────────────┘ │
│  Actions │            │                 ▼                │
└──────────┘            │  ┌─────────────────────────────┐ │
┌──────────┐  queries   │  │  agent loop (tool-use loop)  │─┼──▶ Langfuse
│Prometheus│◀───────────│  │  • get_jira_ticket           │ │    (traces,
│Loki+Graf.│◀───────────│  │  • get_recent_runs / diff    │ │     tokens,
└──────────┘            │  │  • query_metrics/search_logs │ │     cost)
                         │  │  • search_runbooks ──────────┼─┼──▶ pgvector
                         │  │  • submit_postmortem ─────────┼─┼──▶ Jira comment
                         │  └──────────────┬──────────────┘ │
                         └─────────────────┼─────────────────┘
                                            ▼
                              Structured root-cause postmortem
```

## Stack

| Layer | Choice | Why |
|---|---|---|
| Agent + demo service | Python 3.12 + FastAPI | The de-facto AI engineering stack |
| LLM | Anthropic API (tool use), Haiku 4.5 | First-class function calling; cheap enough to run repeatedly |
| Ticket source | Jira Cloud REST API | Real incidents start life as tickets |
| CI/deploy source | GitHub Actions API + compare API | Real workflow failures and real deploy diffs |
| Azure metrics/logs | Log Analytics (KQL) + Azure Monitor Metrics, AAD service principal | For incidents on Azure-hosted infra |
| AWS metrics/logs | CloudWatch Logs + Metrics, access-key auth via boto3 | For incidents on AWS-hosted infra |
| RAG | PostgreSQL + pgvector + Voyage AI, hybrid search (vector + full-text via RRF) | Boring, production-real, no bespoke vector-DB infra |
| Metrics/Logs (optional) | Prometheus / Loki + promtail | Kept from AIInvestigator for synthetic-fault testing |
| LLM tracing | Langfuse (self-hosted) | Full trace tree: spans, generations, tool calls, cost per run |
| Evals | Custom harness + LLM-as-judge | Measured accuracy + quality on injected faults, not vibes |
| Tests | pytest + respx, mocked | Tool-module request/response handling + webhook auth logic |
| UI | React (Vite) + react-router | Multi-page operator console — see Operator console below |
| Auth | Signed session cookie (PyJWT), real per-user accounts (argon2-hashed passwords) | Self-service register/login; every user's data is fully isolated |
| Packaging | Docker Compose | One command up, zero manual clicking |

## Operator console

The UI (`ui/`) is a multi-page app behind a login:

| Route | Page |
|---|---|
| `/` | Public landing page (free, self-hosted, bring your own AI key) |
| `/login` | Sign in |
| `/register` | Create an account |
| `/dashboard` | Integration health, 7-day stats, recent investigations |
| `/investigate` | Manual trigger + live SSE investigation view |
| `/investigations` | Full history, filterable by source/status, paginated |
| `/investigations/:id` | Full postmortem, source links, re-run, mark reviewed |
| `/runbooks` | Ingested runbooks + re-ingest trigger |
| `/settings/integrations` | Which of Jira/GitHub/Azure/AWS/Prometheus/Loki are configured + live "test connection" |
| `/demo` | demo-app fault injection + eval harness trigger/viewer |

All JSON API routes live under `/api/*` and are gated by session auth (checked by `AuthMiddleware` in `agent/main.py`); `/health`, `/webhooks/*`, and `/auth/*` are intentionally public — webhooks authenticate via their own secret/signature, and the SPA shell + `/auth/*` have to be reachable before a session exists.

## Quickstart

```bash
cp .env.example .env
# Fill in: EMBEDDING_API_KEY (Voyage AI), Langfuse secrets, SESSION_SECRET
# (generate with `openssl rand -hex 32`), and whichever of
# JIRA_*/GITHUB_*/AZURE_*/AWS_* you actually have accounts for. Your own AI
# provider key (Claude/OpenAI/compatible) is added from the running app's
# Settings page after you register, not from .env.

make up          # docker compose up -d --build
make investigate  # or open the UI, register an account, and trigger manually
```

Runbooks are seeded per-account automatically on registration (see
`make ingest` in the Makefile if you need to re-embed after adding new
`runbooks/*.md` files for an existing account).

| Service | URL |
|---|---|
| **Operator UI** | http://localhost:8085 |
| Demo shop (fault control API) | http://localhost:8001 |
| Grafana | http://localhost:3300 |
| Prometheus | http://localhost:9090 |
| **Langfuse (traces)** | http://localhost:3301 |

## Running the tests

```bash
make test   # pytest + respx: tool-module request/response handling, webhook auth logic
```

Mocked, no live credentials needed — separate from `make evals`, which scores investigation quality against demo-app faults using the real Anthropic API.

## Wiring up webhooks (local testing)

Jira and GitHub both need a public URL to reach your webhook endpoints. Locally, use a tunnel:

```bash
make tunnel   # ngrok http 8085 — copy the https://*.ngrok-free.app URL it prints
```

**Jira**: Project settings → System → WebHooks → create one pointing at
`https://<tunnel>/webhooks/jira?secret=<JIRA_WEBHOOK_SECRET>`, firing on
issue created (and/or labeled, depending on how you want to scope triggers).

**GitHub**: Repo settings → Webhooks → Add webhook, payload URL
`https://<tunnel>/webhooks/github`, content type `application/json`, secret =
`GITHUB_WEBHOOK_SECRET`, events = "Workflow runs".

For anything beyond local testing, a stable public endpoint (small VPS) is
needed instead of a tunnel — see Build status below.

## Build status

| Phase | Theme | Status |
|---|---|---|
| — | Agent loop, RAG, evals, tracing (inherited from AIInvestigator) | ✅ |
| A | Repo setup, isolated from AIInvestigator | ✅ |
| B | Jira integration (`get_jira_ticket`, webhook, comment-back) | ✅ |
| C | GitHub Actions integration (runs, logs, real deploy diffs, webhook) | ✅ |
| D | Local webhook testing via tunnel | ✅ documented, needs your Jira/GitHub credentials to test live |
| E | React operator UI | ✅ |
| F | Azure Monitor + AWS CloudWatch tools | ✅ code complete, needs your Azure/AWS credentials to test live |
| G | Investigation quality/reliability (calibration, cross-source correlation, retries) | ✅ |
| H | Test coverage (pytest + respx, tool modules + webhook auth) | ✅ 42 passing |
| I | Multi-page operator console: nav shell + routing | ✅ |
| K | Investigation history + detail pages (filters, pagination, mark reviewed, re-run) | ✅ |
| L | Dashboard (integration health, 7-day stats, recent investigations) | ✅ |
| M | Runbooks page (list + re-ingest) | ✅ |
| N | Integrations/Settings page (config status + live test-connection) | ✅ |
| J | Login-gated access (session cookie, real per-user accounts, register/login) | ✅ |

Needs a stable public endpoint (small VPS) instead of a tunnel for anything beyond local testing — not done in this pass.

## Project docs

- **docs/GLOSSARY.md** — every AI-engineering term you'll meet, explained
- **docs/TIPS.md** — hard-won tips & tricks
- **docs/decisions.md** — running log of non-obvious design decisions and why (carried over from AIInvestigator, extended here)
