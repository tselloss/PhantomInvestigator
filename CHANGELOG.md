# Changelog

## 0.1.0 — initial release

- Webhook-triggered investigations from Jira and GitHub Actions, plus Azure DevOps work items and auto-fix PR proposals.
- Tool belt: Jira, GitHub Actions, Azure DevOps, Zendesk, Azure Monitor, AWS CloudWatch, Prometheus, and Loki — each with per-client credential overrides on top of a shared global default.
- RAG-backed runbook search with per-user ingestion.
- Real per-user accounts (username/password and Google sign-in) with fully isolated per-user data, session-cookie auth, and a server-enforced Terms of Service acceptance gate.
- Operator-approval gate before any postmortem is posted back to Jira/Azure DevOps — no autonomous ticket writes.
- Per-user monthly AI spend cap, BYOK AI provider configuration, and per-model cost tracking.
- Multi-page operator console: clients/deployments with edit and archive, per-client aggregated bugs/tasks dashboard, investigation stats with a daily activity breakdown, demo mode.
- Every LLM and tool call traced via a self-hosted Langfuse instance.
