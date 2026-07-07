# Design decisions log

Record every non-obvious choice here as you make it. This file = interview prep.

| Date | Decision | Alternatives considered | Why |
|---|---|---|---|
| 2026-07-06 | No agent framework (raw API + hand-written loop) | LangChain, LlamaIndex | Learn the fundamentals; full control; better interview story |
| 2026-07-06 | pgvector over dedicated vector DB | Qdrant, Pinecone | One less service; Postgres skills transfer; scale is tiny |
| 2026-07-06 | Fault injection doubles as "deploys" | Real git history | Perfect ground truth for evals with zero extra infra |
| 2026-07-07 | Fork AIInvestigator into PhantomInvestigator rather than extend it in place | Add real-source tools directly to AIInvestigator | AIInvestigator stays a clean, self-contained portfolio demo; PhantomInvestigator can carry real credentials, webhooks, and prod-facing risk without touching that |
| 2026-07-07 | Keep demo-app/Prometheus/Loki/Grafana stack in PhantomInvestigator | Strip it down to only real integrations | Lets the agent loop be regression-tested against synthetic faults without needing live prod access |
| 2026-07-07 | Jira webhook auth via shared secret query param, not signature | Jira Cloud has no native payload signing | Practical given the platform constraint; document as a known limitation vs. GitHub's HMAC |
