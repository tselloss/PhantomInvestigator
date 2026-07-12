# Runbook: Disk/storage exhaustion

Signal sources: query_metrics (cAdvisor container_fs_usage_bytes), query_azure_metrics/query_aws_metrics (cloud disk metrics), search_logs/query_azure_logs/query_aws_logs ("No space left on device").

## Symptoms
- Writes start failing — log writes, temp file writes, DB writes — with
  "No space left on device" or an equivalent OS-level error, sometimes after
  a long stretch of otherwise-normal operation
- Container or instance restarts/crash-loops once disk hits 100%, with no
  code deploy correlated to the crash itself
- Usually preceded by a slow, easy-to-miss climb (growing log files, an
  unbounded local cache-to-disk, accumulating temp uploads) rather than a
  single sudden event

## Past incident (2026-01-05)
A logging change meant to be temporary wrote verbose debug output to local
disk instead of the log aggregator. Disk usage climbed steadily over
several days with nothing else visibly wrong, until writes started failing
service-wide once the disk filled — by which point the deploy that actually
caused it was days old and easy to overlook.

## Diagnosis steps
1. Check disk usage trend over the days leading up to the incident, not just
   the incident window itself: container_fs_usage_bytes via query_metrics
   (cAdvisor, filtered to the deployment's container(s)), or the
   cloud-native disk metric via query_azure_metrics/query_aws_metrics.
2. search_logs/query_azure_logs/query_aws_logs for "No space left on
   device", "ENOSPC", or write-failure errors — these typically appear
   before the process fully crashes and are a faster signal than the metric
   trend alone.
3. Identify what's consuming the disk: a recent deploy that changed logging
   verbosity or destination (get_deploy_diff / get_azure_devops_commits), or
   a feature that writes local files without cleanup.
4. Note the climb's actual start time. A slow multi-day climb rules out
   "today's deploy" as the sole cause even if a deploy happens to precede
   the final crash — the real trigger is often much older.

## Fix
Clear or rotate the offending files to restore service immediately; move
verbose/debug logging to the aggregator instead of local disk; add a
disk-usage alert with headroom well before 100%, since this failure mode is
otherwise silent until it's total.
