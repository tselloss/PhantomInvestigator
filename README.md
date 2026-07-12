# 👻 Phantom Investigator

[![tests](https://github.com/tselloss/PhantomInvestigator/actions/workflows/test.yml/badge.svg)](https://github.com/tselloss/PhantomInvestigator/actions/workflows/test.yml)
[![evals](https://github.com/tselloss/PhantomInvestigator/actions/workflows/evals.yml/badge.svg)](https://github.com/tselloss/PhantomInvestigator/actions/workflows/evals.yml)
[![Buy Me A Coffee](https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png)](https://buymeacoffee.com/tsellosskr)

> An AI agent that debugs production incidents like an SRE: reads the Jira/Azure DevOps ticket, checks recent CI/deploy history, queries metrics and logs, cross-references past postmortems (RAG), and writes a root-cause report — every step traced.

Built on the same agent architecture as [AIInvestigator](https://github.com/tselloss/AIInvestigator) (its demo-app/Prometheus/Loki proving ground for the agent loop, kept here for regression testing), extended to investigate **real** production incidents sourced from Jira, Azure DevOps, and GitHub Actions — triggered automatically via webhooks, with results posted back to the ticket.

## How it works

1. A Jira or Azure DevOps ticket gets created/labeled, or a GitHub Actions workflow run fails.
2. A webhook fires (`/webhooks/jira`, `/webhooks/azure_devops`, or `/webhooks/github`), which kicks off an investigation in the background.
3. The agent runs autonomously: reads the triggering ticket or workflow run, checks recent deploy diffs (real GitHub compare API), queries metrics/logs, and searches a runbook knowledge base (hybrid vector + full-text RAG).
4. It returns a structured root-cause postmortem — title, root cause, confidence, timeline, cited evidence, suggested fix, similar past incidents — and, on deployments that opt in, a proposed code fix as a set of file diffs.
5. Nothing externally-visible fires unattended: the ticket comment is queued as a **pending action**, and a proposed fix is queued as a **pending fix action** (opened as a GitHub PR only once approved) for an operator to approve or dismiss from the UI (see Operator console below) — a human-in-the-loop gate on every write the agent can make. Every step (each LLM call, each tool call) is traced in Langfuse, with per-model USD cost estimated and capped per run against a self-service monthly spend cap.

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

*(webhook-triggered `submit_postmortem` → Jira comment is held as a pending action for operator approval, not fired directly — see step 5 above)*

## Stack

| Layer | Choice | Why |
|---|---|---|
| Agent + demo service | Python 3.12 + FastAPI | The de-facto AI engineering stack |
| LLM | Anthropic API (tool use), Haiku 4.5 | First-class function calling; cheap enough to run repeatedly |
| Ticket source | Jira Cloud REST API + Azure DevOps (work items, WIQL search, commits/builds) | Real incidents start life as tickets |
| CI/deploy source | GitHub Actions API + compare API | Real workflow failures and real deploy diffs |
| Support/bug tracking | Zendesk search API | Feeds the per-client aggregated bugs/tasks dashboard alongside Jira/Azure DevOps |
| Azure metrics/logs | Log Analytics (KQL) + Azure Monitor Metrics, AAD service principal | For incidents on Azure-hosted infra |
| AWS metrics/logs | CloudWatch Logs + Metrics, access-key auth via boto3 | For incidents on AWS-hosted infra |
| RAG | PostgreSQL + pgvector + Voyage AI, hybrid search (vector + full-text via RRF) | Boring, production-real, no bespoke vector-DB infra |
| Metrics/Logs (optional) | Prometheus / Loki + promtail | Kept from AIInvestigator for synthetic-fault testing |
| LLM tracing | Langfuse (self-hosted) | Full trace tree: spans, generations, tool calls, cost per run |
| Cost control | Per-model USD pricing table, estimated per call, hard cap per investigation | Stops a runaway loop from burning budget; real cost-per-run instead of just token counts |
| Human-in-the-loop | Pending-action queue for ticket comments and proposed-fix PRs, approve/dismiss from the UI | No externally-visible write fires unattended |
| Auto-fix proposals | GitHub PR built from the postmortem's proposed fix, opt-in per deployment (`allowed_base_branches`), operator-approved | Turns a root-cause fix into a reviewable diff without ever merging on its own |
| Evals | Custom harness + LLM-as-judge | Measured accuracy + quality on injected faults, not vibes |
| Tests | pytest + respx, mocked, run on every push/PR via GitHub Actions | Tool-module request/response handling + webhook auth logic |
| UI | React (Vite) + react-router | Multi-page operator console — see Operator console below |
| Auth | Signed session cookie (PyJWT), real per-user accounts (argon2-hashed passwords), optional "Continue with Google" | Self-service register/login; every user's data is fully isolated |
| Packaging | Docker Compose | One command up, zero manual clicking |

## Operator console

The UI (`ui/`) is a multi-page app behind a login:

| Route | Page |
|---|---|
| `/` | Public landing page (free, self-hosted, bring your own AI key) |
| `/login` | Sign in (username/password or "Continue with Google") |
| `/register` | Create an account |
| `/terms` | Terms of Service (acceptance is server-enforced before any other page loads) |
| `/docs` | In-app documentation |
| `/dashboard` | Integration health, 7-day stats, recent investigations |
| `/investigate` | Manual trigger + live SSE investigation view, plus demo-app fault injection/eval harness |
| `/investigations` | Full history, filterable by source/status/deployment, paginated |
| `/investigations/:id` | Full postmortem, source links, re-run, mark reviewed, approve/dismiss a pending Jira/Azure DevOps comment or fix PR |
| `/clients` | Client/deployment registry (create, edit, archive) + per-client aggregated bugs/tasks dashboard (Jira/Azure DevOps/Zendesk) |
| `/runbooks` | Ingested runbooks + re-ingest trigger |
| `/settings/profile` | Monthly AI spend cap and account settings |
| `/settings/integrations` | Which of Jira/GitHub/Azure DevOps/Zendesk/Azure/AWS/Prometheus/Loki are configured (global and per-client) + live "test connection" |

All JSON API routes live under `/api/*` and are gated by session auth (checked by `AuthMiddleware` in `agent/main.py`); `/health`, `/webhooks/*`, and `/auth/*` are intentionally public — webhooks authenticate via their own secret/signature, and the SPA shell + `/auth/*` have to be reachable before a session exists.

## Quickstart

```bash
make setup       # bootstraps .env: generates every secret it can, asks for the rest
                 # (Anthropic key, Voyage AI key -- both skippable, fill in later)

make up          # docker compose up -d --build
make investigate  # or open the UI, register an account, and trigger manually
```

`make setup` handles SESSION_SECRET, CREDENTIALS_ENCRYPTION_KEY, and all the
Langfuse secrets/keys for you. Jira/GitHub/Azure/AWS are left blank -- wire up
whichever you actually have accounts for, either in `.env` or later from the
Integrations page. Your own AI provider key (Claude/OpenAI/compatible) can
also be added from the running app's Settings page after you register,
instead of `.env`. `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/`GOOGLE_REDIRECT_URI`
are also left blank -- set them to enable "Continue with Google" on the
login/register pages, otherwise username/password stays the only option.

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

For anything beyond local testing, a stable public endpoint is needed instead
of a tunnel — see phase X in Build status below.

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
| H | Test coverage (pytest + respx, tool modules + webhook auth) | ✅ 430 passing, run in CI on every push/PR |
| I | Multi-page operator console: nav shell + routing | ✅ |
| K | Investigation history + detail pages (filters, pagination, mark reviewed, re-run) | ✅ |
| L | Dashboard (integration health, 7-day stats, recent investigations) | ✅ |
| M | Runbooks page (list + re-ingest) | ✅ |
| N | Integrations/Settings page (config status + live test-connection) | ✅ |
| J | Login-gated access (session cookie, real per-user accounts, register/login) | ✅ |
| O | Per-user data isolation (runbooks, investigations, credentials) + BYOK AI provider | ✅ |
| P | Operator-approval gate for Jira posts (human-in-the-loop) + per-model cost tracking/budget cap | ✅ |
| Q | Client/deployment registry with edit + archive (soft-delete), investigations filterable per deployment | ✅ |
| R | Per-client integration credential overrides (all integrations, over a shared global default) | ✅ |
| S | Azure DevOps integration (work items, webhook, commits/builds/WIQL search) + Zendesk ticket search | ✅ |
| T | Per-client aggregated bugs/tasks dashboard (Jira + Azure DevOps + Zendesk) | ✅ |
| U | Auto-fix PR proposals — opt-in per deployment, operator-approved before opening | ✅ |
| V | Terms of Service acceptance gate (server-enforced) + in-app documentation page | ✅ |
| W | Self-service monthly AI spend cap (Profile settings) | ✅ |
| X | Production deployment — live at phantominvestigator.com | ✅ manual SSH/Docker Compose deploy, see `docs/deployment.md`; no CI/CD deploy pipeline yet |

## Project docs

- **docs/GLOSSARY.md** — every AI-engineering term you'll meet, explained
- **docs/TIPS.md** — hard-won tips & tricks
- **docs/decisions.md** — running log of non-obvious design decisions and why (carried over from AIInvestigator, extended here)
- **docs/deployment.md** — manual deploy runbook for the production instance
- **docs/legal/** — Terms of Service, Privacy Policy, and Data Processing Agreement (also served in-app at `/terms` and linked from `/docs`)

## License

All rights reserved — see [LICENSE](LICENSE). This repository is public for
review purposes; it is not open-source, and reuse, redistribution, or running
your own deployment of it is not permitted without written permission.
