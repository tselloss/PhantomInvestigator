# Runbook: Bad migration / schema mismatch

Signal sources: search_logs/query_azure_logs/query_aws_logs (DB/ORM error signatures), get_deploy_diff/get_azure_devops_commits (look specifically for migration files, not just app code).

## Symptoms
- 500s on specific endpoints right after a deploy — superficially like
  bad-deploy-error-spike, but the error is a DB/ORM error, not an unguarded
  field access: "column does not exist", "relation does not exist",
  "UndefinedColumn", or an ORM mapping/attribute error
- Errors are consistent across ALL requests to the affected endpoint/table,
  not a fraction — a schema mismatch breaks every query against that table,
  unlike a conditional bug that only fires on some inputs
- Can depend on migration/deploy ORDERING: app code deployed expecting a
  column the migration hasn't run yet, or new pods roll out ahead of old
  pods finishing requests against the old schema

## Past incident (2026-03-27)
A deploy shipped app code referencing a renamed column, but the migration
that performed the rename ran AFTER the new app code was already serving
traffic — migration and app deploy were part of the same pipeline but not
properly sequenced. Every request touching that table failed for the few
minutes between the app rollout completing and the migration finishing,
then self-resolved once both converged.

## Diagnosis steps
1. search_logs/query_azure_logs/query_aws_logs for DB/ORM error signatures —
   "column ... does not exist", "UndefinedColumn", "relation ... does not
   exist" — as distinct from the app-level KeyError/NullReference pattern in
   bad-deploy-error-spike.
2. get_deploy_diff / get_azure_devops_commits — check specifically for
   migration files, not just application code, and note the migration's
   relationship to the app-code change: same deploy step, or a separate one
   that could run out of order?
3. Check whether ALL requests to the affected endpoint/table fail (points to
   a schema mismatch) versus only a fraction (more consistent with an
   unvalidated-input bug, i.e. bad-deploy-error-spike instead) — this is the
   key disambiguator between the two runbooks.
4. If mid-rollout ordering is suspected, check whether the incident window
   is narrow and matches the rollout duration, self-resolving once all
   pods/migration state converged — that timing signature confirms an
   ordering issue rather than a persistent code bug.

## Fix
Ensure migrations complete BEFORE app code that depends on them starts
serving traffic (migrate-then-deploy, not deploy-then-migrate-eventually).
Prefer backward-compatible schema changes across one deploy cycle
(add-column-first, backfill/migrate data, remove-old-column-later) over
atomic renames that require the app and schema to change in perfect lockstep.
