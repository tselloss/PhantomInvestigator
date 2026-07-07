# Runbook: Downstream dependency failure (payments)

## Symptoms
- 502/504 on endpoints calling the dependency; other endpoints healthy
- Logs full of timeout/connection errors mentioning the provider

## Past incident (2025-11-02)
Payment provider degraded; every checkout waited full timeout then failed.
Mitigated with circuit breaker + cached "retry later" response.

## Diagnosis steps
1. Which endpoints are failing? (group error rate by handler label)
2. Loki: search for "timeout", provider name
3. Check the provider's status page; check if OUR timeout config changed recently

## Fix
Circuit breaker, sane timeouts, graceful degradation path.
