# Runbook: Upstream rate limiting (429s, not timeouts)

Signal sources: search_logs/query_azure_logs/query_aws_logs (429 status + Retry-After), search_support_tickets, query_metrics/query_azure_metrics/query_aws_metrics (our outbound call rate), get_deploy_diff/get_azure_devops_commits.

## Symptoms
- Calls to an upstream/downstream dependency fail with HTTP 429 (Too Many
  Requests), often carrying a Retry-After header — not a timeout or
  connection-refused error
- Failure rate tracks OUR call volume to that dependency, or a recent
  increase in it, rather than tracking the dependency's own health/status
- Often intermittent and bursty rather than a hard outage — some calls
  succeed, others get throttled, especially during peak overlap windows

## Past incident (2026-06-19)
A batch job's schedule was changed to run more frequently, pushing call
volume to a third-party API past its per-minute quota during the hours it
overlapped with regular app traffic. The API began returning 429s only
during that overlap window; outside it, everything looked completely
healthy, which delayed diagnosis until the batch job's own schedule change
was checked.

## Diagnosis steps
1. search_logs/query_azure_logs/query_aws_logs for "429", "rate limit", or
   "quota" near the dependency's client code or provider name — this is the
   key disambiguator from downstream-dependency-failure, whose signature is
   timeouts/connection errors (502/504), not 429s.
2. Check whether OUR call volume to that dependency changed recently — a
   new caller, an increased batch/cron frequency, or a retry storm from an
   unrelated bug — via get_deploy_diff / get_azure_devops_commits. The
   trigger is frequently on our side, not the provider's.
3. query_metrics/query_azure_metrics/query_aws_metrics for our outbound
   request rate to that dependency, correlated against the 429 onset —
   confirm the timing lines up with a volume increase, not a provider-side
   change.
4. Check whether Retry-After values are present and being honored, and
   whether the provider's documented quota is known/available.

## Fix
Back off and retry respecting Retry-After rather than hammering immediately;
request a quota increase if the volume growth is legitimate; add
client-side rate limiting/queueing so outbound calls stay under quota
instead of bursting past it.
