# Runbook: CI/CD pipeline failure (deploy never actually completed)

Signal sources: get_github_runs / get_github_run_logs (GitHub Actions), get_azure_devops_builds / get_azure_devops_commits (Azure Pipelines).

## Symptoms
- The incident starts right around a deploy workflow's timestamp, but the
  workflow/build itself shows a failed or partial conclusion, not success
- The running service reports an older build sha/version than what was
  supposedly just deployed
- On-call chases a code diff for the "latest" commit that was never actually
  shipped, because the deploy that would have shipped it didn't finish

## Past incident (2026-02-18)
A deploy workflow failed partway through — a post-deploy migration step
errored out after the app containers had already restarted, so old app pods
came back up while everyone assumed the new version was live. On-call spent
40 minutes examining the newest merged commit's diff, which had nothing to
do with the symptoms, before checking the workflow run's actual conclusion
and finding it marked "failure."

## Diagnosis steps
1. Check whether the most recent deploy actually succeeded — don't assume a
   recent run means a recent successful deploy:
   - GitHub: get_github_runs(repo) — check conclusion, not just recency
   - Azure DevOps: get_azure_devops_builds(failed_only=true) — try
     failed_only first, it's the fastest way to confirm a broken pipeline
2. If a run/build failed, read what actually broke: get_github_run_logs on
   the failing run_id, or the equivalent build's logs, to see which step
   failed (build, test, migration, deploy)
3. Confirm what's actually running now vs. what was intended: get_deploy_diff
   (GitHub, base...head) or get_azure_devops_commits (Azure) between the
   last known-good release and HEAD — the gap between them is what's
   actually different from what's live
4. Don't treat the newest merged commit as "the deploy" until you've
   confirmed the pipeline that would have shipped it actually completed

## Fix
Fix the failing pipeline step first (often a migration/test step, not the
application code itself); alert on deploy workflow conclusion (failure/
partial), not just on the deploy being triggered — a triggered-but-failed
deploy is easy to mistake for a successful one if nobody checks the
run/build status directly.
