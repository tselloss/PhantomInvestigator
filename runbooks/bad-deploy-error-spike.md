# Runbook: Error spike after deploy

## Symptoms
- Sharp increase in 5xx responses starting minutes after a deploy event
- Stack traces in logs matching newly changed code paths (KeyError, NullReference-style)

## Past incident (2026-01-22)
New discount feature read a request key that wasn't always present; ~30% of
checkouts returned 500. Detected via error-rate alert in 4 minutes.

## Diagnosis steps
1. rate(http_requests_total{status=~"5.."}[5m]) — when did it start?
2. Correlate start time with deploy timestamps
3. Read the deploy diff; look for unguarded dict/property access

## Fix
Rollback first, fix forward second. Add the failing case to tests.
