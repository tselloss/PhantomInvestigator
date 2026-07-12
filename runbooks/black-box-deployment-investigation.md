# Runbook: Black-box client deployment (unknown version/build)

Signal sources: get_deployment_profile, diff_against_known_release, get_diagnostic_bundle_summary, search_diagnostic_bundle, record_version_fingerprint — no live metrics/logs query access assumed.

## Symptoms
- The alert names a deployment id, but get_deployment_profile returns nothing on record: no known version, build sha, or drift history
- No Prometheus/Loki/Azure Monitor/CloudWatch access is configured for this deployment — query_metrics/search_logs/query_azure_*/query_aws_* either aren't reachable or return nothing relevant
- The only available evidence is whatever a support engineer or the client uploaded as a diagnostic bundle, plus whatever the ticket/support text says

## Past incident (2026-05-06)
A client-hosted instance filed a ticket describing intermittent 500s with no
further detail. get_deployment_profile showed no prior fingerprint — this
client's instance had never been investigated before and self-reports
nothing. A diagnostic bundle had been uploaded containing a partial log
excerpt and a config file. search_diagnostic_bundle over the config turned up
a version string in a comment corresponding to a release from ~8 months
earlier, missing a since-patched bug matching the reported symptom.
record_version_fingerprint was called with that reconstruction at 0.6
confidence — low, but enough for the next investigation on this deployment to
start from a baseline instead of zero.

## Diagnosis steps
1. Call get_deployment_profile FIRST, before anything else. If it already has
   a version/build on record (self-reported, uploaded, or reconstructed from
   a past investigation), skip straight to diff_against_known_release instead
   of treating this as black-box.
2. If nothing is on record, call get_diagnostic_bundle_summary to see what
   was uploaded and what it covers (logs? config? metrics export?) before
   searching blindly.
3. Use search_diagnostic_bundle with targeted queries: version strings,
   config keys, stack trace fragments, dependency versions — treat this as
   your only "logs" and "metrics" source when no live query access exists.
4. As soon as ANY hypothesis forms about version/build/drift — even a
   low-confidence guess like "roughly version 1.4.x, missing a known
   rate-limiter patch" — call record_version_fingerprint immediately. Do not
   wait until you're certain or until submit_postmortem: the investigation
   can end on its step/cost budget before you get there, and an unrecorded
   guess helps nobody next time.
5. If diff_against_known_release becomes possible after a fingerprint is
   recorded, use it to check what deviates from the vendor's stock release
   (different build, local patches, changed config fields) rather than
   assuming this instance matches whatever the vendor's repo has at HEAD.

## Fix
There often isn't a code fix available in this pass — the deliverable is
narrowing down what's actually running. Recording the fingerprint (even a
partial, low-confidence one) is itself the fix: it converts "nobody knows
what this client is running" into a permanent record that every future
investigation for this deployment can build on via get_deployment_profile,
instead of starting from zero each time.
