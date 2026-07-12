# Runbook: Config/feature-flag regression (no code change)

Signal sources: get_deploy_diff / get_azure_devops_commits (to confirm the change is config/flag-only, not application code), query_metrics/query_azure_metrics/query_aws_metrics, search_logs/query_azure_logs/query_aws_logs.

## Symptoms
- A behavior regression correlates with a "deploy" whose diff contains only
  a config file, feature-flag value, or environment variable change — zero
  application code changed
- No exception/stack-trace pattern matching new code, because no new code
  path was added — instead, a previously-dormant path is now reachable, or a
  previously-active path is now disabled
- Impact may ramp rather than step-change instantly, if the flag/config is a
  staged or percentage-based rollout rather than a single global toggle

## Past incident (2026-04-02)
A feature flag was flipped to 100% rollout without a canary stage. The
flagged code path had never been exercised at full production traffic
before and buckled under load — timeouts and elevated latency appeared
within minutes, even though the "deploy" that triggered it was a one-line
flag-service config change with no application code involved.

## Diagnosis steps
1. Get the diff for the suspect deploy: get_deploy_diff (GitHub) or
   get_azure_devops_commits (Azure). If it touches only a config file, flag
   value, or environment variable — not application code — this runbook
   applies instead of a code-level bad-deploy story.
2. Do not force config-only changes into "new code shipped" reasoning: the
   mechanism here is a previously-untested path becoming active (or an
   active path going dark), not a bug in newly-written code. A deploy having
   happened is not, by itself, evidence that new code is the cause.
3. Correlate the flag/config change timestamp precisely against metric/error
   onset via query_metrics/query_azure_metrics/query_aws_metrics — staged or
   percentage rollouts can lag or ramp rather than shift instantly, unlike a
   code deploy's usually-immediate effect.
4. Scope search_logs/query_azure_logs/query_aws_logs to the specific
   endpoint or path the flag/config gates, not just service-wide signals —
   the blast radius is often narrower than "the whole service."

## Fix
Roll back the config/flag value first — this is normally the fastest
mitigation available since no code deploy or rollback is needed. Longer
term: require the same canary/percentage-rollout and monitoring window for
flag and config changes that code deploys already get, rather than treating
them as lower-risk because they skip the build pipeline.
