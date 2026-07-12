# Runbook: TLS/certificate expiry

Signal sources: search_logs/query_azure_logs/query_aws_logs (handshake/certificate errors), query_metrics/query_azure_metrics/query_aws_metrics (all-traffic error cliff), get_recent_changes/get_deploy_diff/get_azure_devops_commits (used to confirm the ABSENCE of a correlated change).

## Symptoms
- Sudden, total failure of a specific integration or endpoint — all
  requests, not a percentage — starting at a specific timestamp
- No corresponding deploy, config change, or traffic change anywhere near
  the incident start
- Errors explicitly mention certificate/TLS/SSL: "certificate has expired",
  "certificate verify failed", handshake failures
- Often scoped to one dependency or one internal service-to-service call
  (whichever cert actually expired), not the whole system

## Past incident (2026-05-30)
An internal service-to-service TLS certificate wasn't on the automated
renewal rotation and expired at midnight. Every call to that service began
failing instantly with a handshake error. There was zero code or config
change anywhere near the incident time, which was itself the strongest clue
once get_deploy_diff and get_azure_devops_commits both came back empty for
the relevant window.

## Diagnosis steps
1. Check whether get_recent_changes / get_deploy_diff /
   get_azure_devops_commits show NOTHING near the incident start. This is
   the strongest signal for this runbook specifically: nearly every other
   incident in this corpus correlates with a change, this one deliberately
   doesn't — a clean diff should raise this runbook's likelihood, not be
   treated as a dead end.
2. search_logs/query_azure_logs/query_aws_logs for "certificate", "SSL",
   "TLS", or "handshake" near the failing calls.
3. Check the exact failure time against any known certificate expiry or
   rotation schedule for the affected dependency, if one is documented.
4. Confirm the failure is total (100% of calls to that dependency) rather
   than partial or gradual — a partial or ramping failure points to a
   different runbook (rate limiting, cache stampede, config rollout).

## Fix
Renew/rotate the certificate immediately to restore service. Put the
certificate on automated renewal and add an expiry-date alert with enough
lead time to act — unlike most incidents in this corpus, this failure mode
is entirely predictable in advance and shouldn't require an incident to
catch.
