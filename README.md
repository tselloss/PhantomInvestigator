# 👻 Phantom Investigator

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
| RAG | PostgreSQL + pgvector + Voyage AI, hybrid search (vector + full-text via RRF) | Boring, production-real, no bespoke vector-DB infra |
| Metrics/Logs (optional) | Prometheus / Loki + promtail | Kept from AIInvestigator for synthetic-fault testing |
| LLM tracing | Langfuse (self-hosted) | Full trace tree: spans, generations, tool calls, cost per run |
| Evals | Custom harness + LLM-as-judge | Measured accuracy + quality on injected faults, not vibes |
| UI | React (Vite) | Operator console: manual trigger, live investigation view, webhook activity feed |
| Packaging | Docker Compose | One command up, zero manual clicking |

## Quickstart

```bash
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, EMBEDDING_API_KEY (Voyage AI), Langfuse secrets,
# and JIRA_*/GITHUB_* credentials once Phase B/C tools are wired up.

make up          # docker compose up -d --build
make ingest       # embed runbooks/*.md into pgvector
make investigate  # or open the UI and trigger manually
```

| Service | URL |
|---|---|
| **Operator UI** | http://localhost:8085 |
| Demo shop (fault control API) | http://localhost:8001 |
| Grafana | http://localhost:3300 |
| Prometheus | http://localhost:9090 |
| **Langfuse (traces)** | http://localhost:3301 |

## Build status

| Phase | Theme | Status |
|---|---|---|
| — | Agent loop, RAG, evals, tracing (inherited from AIInvestigator) | ✅ |
| A | Repo setup, isolated from AIInvestigator | ✅ |
| B | Jira integration (`get_jira_ticket`, webhook, comment-back) | ⬜ in progress |
| C | GitHub Actions integration (runs, logs, real deploy diffs, webhook) | ⬜ |
| D | Local webhook testing via tunnel | ⬜ |
| E | React operator UI | ⬜ |
| F | Azure Monitor + AWS CloudWatch tools | ⬜ deferred |

## Project docs

- **docs/GLOSSARY.md** — every AI-engineering term you'll meet, explained
- **docs/TIPS.md** — hard-won tips & tricks
- **docs/decisions.md** — running log of non-obvious design decisions and why (carried over from AIInvestigator, extended here)
