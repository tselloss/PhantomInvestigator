# 💡 Tips & Tricks (learn these the fast way)

## Working with LLMs

1. **Temperature 0 for agents.** You want reproducibility for debugging and evals. Save creativity for marketing copy.
2. **Prompts live in files, not string literals.** `agent/prompts/investigator.md`. Version them in git; you'll want the diff when an eval regresses.
3. **Tool descriptions are 50% of your prompt engineering.** A tool named `search_logs` with description "Search Loki logs using LogQL, e.g. `{app=\"demo\"} |= \"error\"`. Returns up to 50 lines." works dramatically better than "searches logs".
4. **Truncate everything a tool returns.** One fat log query can blow your context and your budget. Cap lines, cap chars, tell the model it was truncated.
5. **Cap the loop.** `MAX_STEPS = 10`. Agents without caps go on €20 sightseeing tours of your metrics.
6. **Let tools fail as text.** Return `"ERROR: Loki unreachable"` as the tool result — models recover from that surprisingly well. Exceptions crashing the loop teach the model nothing.
7. **Log full raw requests/responses in dev.** When the agent acts weird, the answer is always in the exact JSON you sent.
8. **Pin your model version.** `claude-sonnet-x-y`, not "latest". Model upgrades silently change behavior; your evals tell you when it's safe to move.

## RAG

9. **Garbage in, garbage retrieved.** One hour cleaning/structuring runbooks beats ten hours tuning retrieval.
10. **Cache embeddings by content hash.** Re-ingesting unchanged docs is pure wasted money.
11. **Look at what retrieval actually returns** before blaming the LLM. 80% of "RAG is bad" = irrelevant chunks retrieved.
12. **Keywords matter for ops content.** Error codes and service names are exact strings — that's why hybrid search wins here.

## Evals

13. **Write the first eval the same day you write the first prompt.** Even 5 cases. Everything after that is measurable.
14. **Log cost per eval run.** "Diagnoses 85% of incidents at €0.04 each" is a sentence that gets you hired.
15. **Never trust one run.** LLMs are stochastic even at temp 0 (tool results vary). Run each case 3–5×, report the rate.

## Money

16. **Set a hard monthly budget in the API console.** Do it today.
17. **Develop against cheap models (Haiku), eval against the real one.** Most bugs are loop/tool bugs — no need to pay Sonnet prices to find them.
18. **A whole eval suite run should cost cents, not euros.** If not, your context is bloated — go find what you forgot to truncate.

## Python for the C# refugee

19. `pydantic.BaseModel` = your C# record/DTO + validation. Use it everywhere: API bodies, tool schemas, agent output.
20. `uv` is the modern package manager (fast, lockfiles) — think NuGet + venv in one. `pip` is fine to start.
21. Type-hint everything and run `mypy`/`pyright` — recreates the C# safety net.
22. `httpx` = `HttpClient` (sync + async). `structlog` = Serilog. `pytest` = xUnit but terser.
23. Format with `ruff` on save and never think about style again.

## Portfolio & job search

24. **README is the product.** GIF first, architecture diagram, eval table, honest limitations. Most reviewers never run the code.
25. **Commit daily, even 10 lines.** The contribution graph is checked more than the code.
26. **An "What I'd do next" section** (multi-model routing, MCP tools, K8s events source) signals senior judgment — you know what you cut and why.
27. **Write down every design decision** in `docs/decisions.md` as you go. That file is literally your interview prep.
28. **Ship at week 4, not week 8.** Push the repo public early with "WIP" — early stars/feedback beat a big reveal.

## Traps to avoid

- ❌ Starting with LangChain "to be professional" — you'll fight the framework instead of learning the concepts.
- ❌ Building UI before the agent works — the agent IS the product.
- ❌ Fine-tuning anything — not needed here, ever.
- ❌ Ten fault types — four *reliably diagnosable* ones beat ten flaky ones.
- ❌ Perfect Python — working, typed, formatted is enough; you're an AI engineer, not a CPython maintainer.
