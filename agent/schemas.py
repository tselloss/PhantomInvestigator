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

class Postmortem(BaseModel):
    title: str
    root_cause: str
    fault_category: str = Field(description=(
        "Categorize by the FAILURE MECHANISM you found, not by whether a deploy diff "
        "exists — in this environment every fault correlates with a recent deploy, so "
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
        "unknown (evidence doesn't clearly match any of the above)."
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
