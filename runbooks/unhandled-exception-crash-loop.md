# Runbook: Unhandled exception crash-loop (no deploy, no resource trend)

Signal sources: search_logs/query_azure_logs/query_aws_logs (repeating crash/stack-trace signature), query_metrics/query_azure_metrics/query_aws_metrics (restart/churn count, not a resource metric climbing), get_recent_changes/get_deploy_diff/get_azure_devops_commits (used to confirm the ABSENCE of a correlated change).

## Symptoms
- The service crashes and restarts repeatedly, with the SAME unhandled
  exception/stack trace appearing right before each crash
- No deploy, config change, or resource-growth trend correlates with the
  onset — the bug has often been live for a long time and was only
  triggered now by a specific, unusual production input
- Doesn't fit memory-leak (no gradual climb beforehand) or
  bad-deploy-error-spike (no recent deploy) — the trigger is a specific
  input hitting a latent code path, not a change to the system

## Past incident (2026-04-19)
A service began crash-looping with an unhandled exception in a rarely-used
parsing branch. No deploy had happened in over a week and no resource
metric showed any climb beforehand. The crash only started once a specific
customer began sending a request shape the code had never handled, which
had simply never occurred in production before that day.

## Diagnosis steps
1. Confirm get_recent_changes / get_deploy_diff / get_azure_devops_commits
   show NOTHING correlated with the crash onset — like tls-cert-expiry,
   the absence of a change is itself the signal here, not a dead end.
   Resist the urge to blame "the last deploy on record" just because it's
   the newest change available; if it predates the crash onset by days, it
   probably isn't the cause.
2. search_logs/query_azure_logs/query_aws_logs for the crash's stack trace
   — since this is a loop, the same exception should repeat identically
   each restart. Find the specific request/input logged immediately before
   each crash, not just the exception type.
3. query_metrics/query_azure_metrics/query_aws_metrics for restart count or
   container churn (e.g. cAdvisor container uptime resets) to confirm the
   loop's frequency and exact start time — this is a churn signal, not a
   resource metric trending upward.
4. Identify what's unusual about the specific triggering input (an
   unexpected field, size, encoding, or value) rather than assuming
   something about the surrounding infrastructure changed.

## Fix
Patch the specific unhandled case (validate/guard the input rather than
letting it reach the code that throws); add the exact triggering input as a
regression test; add a crash-loop/restart-count alert distinct from the
resource-trend alerts the other runbooks rely on, since this failure mode
produces no resource ramp to alert on beforehand.
