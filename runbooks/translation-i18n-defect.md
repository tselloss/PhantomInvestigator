# Runbook: Translation / i18n defect (single-locale)

Signal sources: search_support_tickets (reports naming a specific language), get_deploy_diff/get_azure_devops_commits (scoped to locale/translation files, not application code), search_logs/query_azure_logs/query_aws_logs (missing-translation-key warnings, if logged).

## Symptoms
- Users in one specific locale/language report broken or missing text:
  raw translation keys showing instead of real text, garbled/mojibake
  characters, wrong pluralization, or text overflowing its UI container
- Other locales are completely unaffected
- No backend error and no metric movement — this is a content/rendering
  defect, not a functional failure, so it won't show up in error-rate or
  latency signals at all

## Past incident (2026-01-29)
A locale file update shipped with a malformed key. Users in that one
language saw raw key strings on a specific page immediately after the
deploy; every other locale rendered correctly, and no backend error or
metric moved — the only signal was support tickets naming the affected
language specifically.

## Diagnosis steps
1. search_support_tickets for reports naming a specific language or
   describing garbled/raw-key text — this class of defect is almost always
   surfaced by users, not detected by any metric or log-based alert.
2. get_deploy_diff/get_azure_devops_commits scoped to locale/translation
   files (e.g. files under a locale directory, *.json/*.po/*.resx) rather
   than application code.
3. search_logs/query_azure_logs/query_aws_logs for missing-translation-key
   or fallback warnings, if the i18n framework logs them — a faster
   confirmation than manually diffing the locale file.
4. Confirm the blast radius is limited to the affected locale(s) before
   treating this as urgent/global — a single-locale defect has a narrow,
   cheap fix, unlike a defect that turns out to affect the base/fallback
   locale (which would then affect everyone).

## Fix
Revert or correct the malformed locale file; add a CI check that validates
translation files (well-formed syntax, no missing keys relative to the
base locale) before merge, since this defect class ships silently past any
check that only looks at application code.
