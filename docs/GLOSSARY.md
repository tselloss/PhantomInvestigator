# 📖 AI Engineering Dictionary

Every term you'll hit in this project (and in interviews), explained for an engineer — with .NET analogies where they help.

## LLM fundamentals

- **Token** — the unit LLMs read/write; ~¾ of an English word. You pay per token, in and out. `"investigating"` ≈ 3 tokens.
- **Context window** — the model's working memory per request (e.g. 200k tokens). Everything — system prompt, history, tool results — must fit. There is no memory *between* requests; you resend state every time (LLMs are stateless, like HTTP).
- **System prompt** — the instructions defining the model's role and rules. Think of it as configuration + interface contract in natural language.
- **Temperature** — randomness dial. 0 ≈ deterministic (use for agents/evals), ~1 = creative.
- **Streaming** — receiving tokens as they generate (SSE), like `IAsyncEnumerable` for the response.
- **Hallucination** — confident fabrication. The fix isn't "better prompts", it's grounding (give the model real data) + evals (measure it).
- **Grounding** — anchoring model answers to supplied facts (tool results, retrieved docs) instead of its training memory.
- **Few-shot** — putting worked examples in the prompt so the model imitates the pattern. Often beats lengthy instructions.
- **Fine-tuning** — retraining a model on your data. You almost never need it; RAG + prompting covers 95% of cases. Great interview answer: "I'd exhaust RAG and prompting first because they're cheaper, inspectable, and instantly updatable."

## Agents & tools

- **Tool use / function calling** — you describe functions (JSON Schema); the model responds with "call `search_logs` with these args"; *your code* executes it and returns the result. The model never runs anything itself — it's an RPC where the model is the caller.
- **Agent** — an LLM in a loop with tools and a goal. That's the whole secret.
- **Agent loop** — `while model_wants_tools: execute(); append_results()`. Always cap max steps.
- **ReAct** — the classic pattern: Reason → Act → observe → repeat. Modern tool use does this natively.
- **Structured output** — forcing responses into a schema (pydantic model), so downstream code parses objects, not prose.
- **Orchestration frameworks** — LangChain, LlamaIndex, etc. This project deliberately skips them: raw API + a hand-written loop teaches more and impresses interviewers more ("I understand what the framework abstracts").
- **MCP (Model Context Protocol)** — an open standard for exposing tools/data to models, like a USB port for AI tools. Know the name; adopting it here is a stretch goal.

## RAG

- **Embedding** — a text→vector function where similar meaning ⇒ nearby vectors. Enables "search by meaning".
- **Vector database** — stores embeddings, answers "give me the k nearest vectors". We use **pgvector** (a Postgres extension) — boring on purpose.
- **Cosine similarity** — the standard "how close are two vectors" measure (angle between them).
- **Chunking** — splitting documents before embedding. The #1 lever for RAG quality. Chunk by semantic units (markdown sections), keep headings attached.
- **Top-k** — retrieve the k most similar chunks (typically 3–8).
- **RAG (Retrieval-Augmented Generation)** — retrieve relevant chunks → stuff into prompt → model answers grounded in them. It's "give the model an open-book exam".
- **Hybrid search** — vector search + keyword (full-text) search combined. Keywords catch exact terms (error codes!) that embeddings fuzz over.
- **Reranking** — a second, more accurate model re-sorts the retrieved candidates. Cheap quality boost.
- **HNSW** — the index type that makes vector search fast. Just know: "approximate nearest neighbor index; trades a little recall for a lot of speed."

## Evals & quality

- **Eval** — automated tests for LLM behavior. Unit tests assert exact outputs; evals *score* fuzzy outputs against criteria. No evals = no engineering, just vibes.
- **Golden dataset** — curated inputs with known correct answers. Ours: injected faults with known root causes. This is the project's superpower — perfect ground truth for free.
- **LLM-as-judge** — using a strong model to grade another model's output against a rubric. Standard practice for fuzzy criteria ("is this postmortem actionable?").
- **Rubric** — the explicit grading criteria you give the judge. Vague rubric = useless scores.
- **Regression** — a prompt/model change that silently makes things worse. Evals on every change catch it, exactly like CI tests.

## Production concerns

- **Tracing / spans** — recording each step of an agent run (every LLM call, every tool call) with timing and cost. Langfuse = "Application Insights for LLM apps".
- **Prompt injection** — malicious instructions hidden in data the model reads (logs, docs, web pages). *The* security issue of AI engineering. Treat all retrieved/tool content as untrusted input.
- **Guardrails** — hard limits around the model: max steps, cost budgets, output validation, blocked actions.
- **Rate limiting / backoff** — LLM APIs throttle you; retry with exponential backoff, same as any flaky HTTP dependency.
- **Latency vs. cost vs. quality** — the eternal triangle. Big model = better + slower + pricier. Route easy tasks to small models. Have an opinion on this in interviews.

## Observability (SRE-side)

- **PromQL** — Prometheus query language. `rate(http_requests_total{status="500"}[5m])` = 500s per second over the last 5 min.
- **LogQL** — Loki's query language, PromQL-flavored log search: `{app="demo"} |= "timeout"`.
- **Cardinality** — number of unique label combinations on a metric. High cardinality (e.g. user-id labels) kills Prometheus. Classic interview trap.
- **p95 / p99** — 95th/99th percentile latency. "p99 = 2s" → the slowest 1% of requests take ≥2s. Averages lie; percentiles don't.
- **SLO / SLI** — Service Level Indicator = what you measure (error rate); Objective = the target (99.9%).
- **Runbook** — a "when X breaks, do Y" doc. Our RAG corpus.
- **Postmortem** — the structured incident write-up (timeline, root cause, impact, action items). Our agent's final deliverable.
- **Blameless** — postmortem culture: analyze systems, not people. Use the word; SREs will nod.
