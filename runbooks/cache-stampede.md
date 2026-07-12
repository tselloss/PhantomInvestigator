# Runbook: Cache stampede / mass cache miss

Signal sources: query_metrics/query_azure_metrics/query_aws_metrics (DB or origin query rate, not just latency), search_logs/query_azure_logs/query_aws_logs (cache hit/miss/eviction messages), get_recent_changes/get_deploy_diff/get_azure_devops_commits.

## Symptoms
- p95/p99 latency climbs sharply on read-heavy endpoints, with a burst of DB
  or origin load, not a steady climb
- Looks like db-connection-pool-exhaustion at first glance (latency up, CPU
  moderate, no immediate errors) — the disambiguator is the SHAPE of the
  spike: this one is a sharp burst tied to a specific moment, not a gradual
  saturation ramp
- Often coincides with a cache-serving process restart, a deploy that
  flushed or cold-started the cache, or a synchronized TTL expiry across
  many keys at once

## Past incident (2025-12-11)
A deploy restarted the cache-serving pods as a side effect (unrelated to the
cache itself), cold-starting the in-process cache. The next traffic burst
all missed cache simultaneously and hit the DB directly, producing a latency
spike that read exactly like a connection-pool problem until DB query
volume — not pool wait time — was actually checked.

## Diagnosis steps
1. Compare the timing signature to db-connection-pool-exhaustion: a
   cache-stampede event produces a SHARP spike in DB/origin query RATE, not
   the gradual ramp-then-plateau of a shrunk connection pool. Check
   query_metrics/query_azure_metrics/query_aws_metrics for query rate (not
   just latency) over the incident window.
2. Check whether a deploy or restart happened right before the spike —
   get_recent_changes / get_deploy_diff / get_azure_devops_commits — since
   an in-process or restartable cache cold-starts on restart even when the
   deploy itself had nothing to do with caching.
3. search_logs/query_azure_logs/query_aws_logs for cache miss/eviction
   messages, or a sudden absence of the usual cache-hit log volume right at
   incident start.
4. Rule out pool exhaustion specifically: pool exhaustion shows
   queueing/wait-time errors from the connection pool itself
   ("PoolError", "waiting for connection"); a cache stampede shows normal
   queries, just far more of them at once, with no pool-level error.

## Fix
Add jitter to cache TTLs so keys don't all expire in the same instant; warm
the cache before routing production traffic to a freshly restarted
instance; consider request-coalescing/lock-on-miss for hot keys so a
simultaneous miss storm collapses into one origin fetch instead of many.
