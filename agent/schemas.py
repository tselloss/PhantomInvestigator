"""Structured output for the final answer (Week 4)."""
from pydantic import BaseModel, Field

class Evidence(BaseModel):
    source: str = Field(description="which tool produced this, e.g. 'query_metrics'")
    detail: str

class ContributingFactor(BaseModel):
    """A distinct issue found during investigation that is NOT the primary
    root cause — e.g. a second, unrelated deploy or a resource-growth issue
    happening at the same time. Incidents can have more than one cause;
    this is where the second one goes instead of being dropped."""
    description: str
    fault_category: str = Field(description="best-guess category, same enum as Postmortem.fault_category")
    evidence: list[Evidence] = Field(default_factory=list)

class FileEdit(BaseModel):
    path: str = Field(description=(
        "Repo-relative path, e.g. 'tests/checkout_flow.spec.js'. Must be a file you "
        "read IN FULL with get_file_contents earlier in this investigation — never a "
        "file you haven't read, and never a new file (editing existing files only)."
    ))
    content: str = Field(description=(
        "The file's COMPLETE new content, not a diff or a snippet — this replaces the "
        "current content verbatim, so it must include every unchanged line too."
    ))

class Postmortem(BaseModel):
    title: str
    root_cause: str
    fault_category: str = Field(description=(
        "Categorize by the FAILURE MECHANISM you found, not by whether a deploy diff "
        "exists — on demo-shop every fault correlates with a recent deploy, so "
        "'a deploy happened' is not sufficient evidence for 'bad_deploy' specifically. "
        "One of: "
        "slow_db (a resource like a DB connection pool is exhausted, causing requests "
        "to queue and latency to spike, with no crash); "
        "bad_deploy (new code raises an exception/crash on a fraction of requests, "
        "e.g. a KeyError from an unvalidated field); "
        "memory_leak (a resource grows unbounded over time, e.g. a cache with no "
        "eviction, trending toward gradual degradation or OOM — not an immediate crash); "
        "error_spike (a downstream dependency times out or fails, causing the request "
        "itself to error out, e.g. a misconfigured timeout to a payment provider); "
        "unknown (evidence doesn't clearly match any of the above). "
        "These four categories describe demo-shop's synthetic fault taxonomy. For a "
        "real (non-demo) incident that doesn't clearly fit one of them, use 'unknown' "
        "here and put the actual explanation in root_cause/contributing_factors — do "
        "not force-fit a real incident into the wrong demo category just to avoid "
        "'unknown'."
    ))
    confidence: float = Field(ge=0, le=1)
    timeline: list[str]
    evidence: list[Evidence]
    suggested_fix: str
    similar_past_incidents: list[str] = []
    contributing_factors: list[ContributingFactor] = Field(
        default_factory=list,
        description=(
            "Other DISTINCT issues found during investigation that are NOT the "
            "primary root cause above — e.g. a second unrelated deploy, or a "
            "resource-growth issue happening at the same time. Empty list if "
            "you found only one issue. Do not fold a second cause into "
            "root_cause/fault_category above — if you noticed something else "
            "going on, report it here instead of silently ignoring it."
        ),
    )
    proposed_fix_files: list[FileEdit] | None = Field(
        default=None,
        description=(
            "A concrete, ready-to-commit code fix (one or a few files) — ONLY when you "
            "found a fix specific enough to commit as-is, and only for files you already "
            "read in full via get_file_contents this run. Leave null for most "
            "investigations; suggested_fix (free text) above is still required either "
            "way. This may become a pull request an operator reviews and approves, so "
            "keep changes minimal and scoped to the root cause."
        ),
    )
