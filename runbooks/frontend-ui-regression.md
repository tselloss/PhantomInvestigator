# Runbook: Frontend/UI regression (backend looks healthy)

Signal sources: search_support_tickets (usually the first, sometimes only, signal), get_deploy_diff/get_github_run_logs or get_azure_devops_builds (frontend-only deploy/build step).

## Symptoms
- Backend metrics and logs show nothing wrong — normal error rate, normal
  latency — but users report a broken page, blank screen, a button that
  does nothing, or visibly broken layout
- Often follows a frontend-only deploy (JS bundle, CSS, static assets) with
  no backend service code change at all
- May be scoped to a specific browser, device, or locale rather than
  affecting every user

## Past incident (2026-03-11)
A frontend deploy shipped a JS bundle referencing a renamed API response
field. The backend was completely healthy the entire time and returned
200s throughout — but the UI silently failed to render the checkout button
because a client-side property access threw before the button mounted. The
only signal was a cluster of Zendesk tickets saying "the page just doesn't
work"; no server-side metric or log ever moved.

## Diagnosis steps
1. Since backend telemetry may show nothing abnormal, don't stop at "no
   error-rate spike, so no real incident" — when the ticket source
   suggests a UI complaint (blank page, "nothing happens when I click",
   broken layout, images not loading), treat a cluster of those tickets via
   search_support_tickets as the primary evidence, not a footnote.
2. get_deploy_diff/get_github_run_logs (or get_azure_devops_builds) for a
   frontend-only deploy correlated with the report time — bundle/asset/
   build-step changes, not backend service changes.
3. Check whether a backend API response shape changed underneath the
   frontend even without a backend-side error — the backend can correctly
   return a different shape while the frontend silently fails to parse or
   render it, producing zero backend-visible errors.
4. Note any browser/device/locale pattern in the ticket text — a defect
   scoped to one rendering path is a much narrower (and different) fix than
   a global outage.

## Fix
Roll back the frontend deploy; add contract tests between frontend and
backend response shapes so a field rename surfaces in CI instead of
production, since this class of incident is invisible to backend-only
monitoring by design.
