# Phantom Investigator
<!-- token-kit. Loaded on every Claude turn: keep it under ~80 lines, facts only. -->
Autonomous SRE-style AI agent, live in production: investigates incidents (metrics, logs, deploys, RAG over postmortems) and writes root-cause reports.

## Stack
- `agent/`: Python FastAPI, Anthropic + OpenAI SDKs, Postgres + pgvector, Langfuse tracing, Azure Monitor / CloudWatch / Azure DevOps integrations
- `ui/`: React + Vite (oxlint)
- `demo-app/`: FastAPI app with Prometheus metrics used as an incident target

## Commands
- Tests: `cd agent && python -m pytest tests/ -q` · one: `pytest tests/test_<name>.py -q`
- Stack: `make up` / `make down` · Seed: `make load ingest` · Evals: `make evals` (costs API tokens; run only when asked)
- UI: `cd ui && npm run dev`

## Layout
- `agent/main.py` app entry; `agent/routes/` HTTP routes; `agent/loop.py` agent loop
- `agent/tools/` investigation tools (one file per integration); `agent/rag/`; `agent/prompts/`
- `agent/evals/` eval suite; `agent/tests/` pytest (`conftest.py` fixtures)
- `runbooks/` RAG source docs; `monitoring/`; `scripts/deploy/`

## Conventions
- New integration = `agent/tools/<name>.py` + `agent/tests/test_<name>.py` with mocked HTTP; never call real cloud APIs in tests
- Settings via `agent/settings.py` (env vars); never hardcode credentials
- Update `CHANGELOG.md` and `VERSION` for user-facing changes

## Working rules
- One task per session; /clear between tasks (`/handoff` first). Plans in docs/plan.md.
- Global token rules: ~/.claude/CLAUDE.md
