# Runbook: Database connection pool exhaustion

## Symptoms
- p95/p99 latency climbs on DB-heavy endpoints (checkout, orders) while error rate stays low at first
- Logs show queries queueing / "waiting for connection" style messages
- CPU normal; the service is *waiting*, not working

## Past incident (2026-03-14)
A deploy reduced POOL_SIZE from 20 to 2 as part of a "resource optimization".
Checkout p95 went from 120ms to 3.8s within 10 minutes. Rolled back in 22 minutes.

## Diagnosis steps
1. histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) — is latency up?
2. Check recent deploys for pool/DB config changes
3. Loki: {container=~".*demo.*"} |= "pool"

## Fix
Restore pool size; longer term: alert on pool saturation, load-test config changes.
