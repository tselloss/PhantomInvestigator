# Runbook: Dependency/package upgrade breakage

Signal sources: get_deploy_diff/get_azure_devops_commits (manifest/lockfile-only changes), get_github_runs/get_github_run_logs or get_azure_devops_builds(failed_only=true), search_logs/query_azure_logs/query_aws_logs (import/load error signature). Ecosystem-agnostic: npm (package.json/package-lock.json), Python (requirements.txt/poetry.lock/pyproject.toml), .NET (*.csproj/packages.lock.json), etc.

## Symptoms
- A dependency version bump — visible only in a lockfile/manifest change,
  not application code — is immediately followed by a build failure or a
  runtime crash at startup/import time
- The bump looks minor/patch-level and "should" be safe, but a transitive
  dependency's breaking change wasn't caught by CI, only surfacing under
  production conditions CI doesn't exercise
- Error signature is ecosystem-specific but always at load/import time, not
  mid-request: "ModuleNotFoundError"/"ImportError" (Python), "Cannot find
  module" (npm), "Could not load file or assembly"/"MissingMethodException"
  (.NET)

## Past incident (2026-02-27)
An automated dependency bot bumped a package's minor version. CI passed —
the tests that ran never touched the affected code path. In production,
the app crashed at startup with a missing-method error, because a
transitive dependency two levels down had made a breaking change that the
minor-version bump pulled in silently.

## Diagnosis steps
1. Check the deploy diff for manifest/lockfile-only changes (package.json/
   package-lock.json, requirements.txt/poetry.lock/pyproject.toml,
   *.csproj/packages.lock.json) rather than application code —
   get_deploy_diff / get_azure_devops_commits.
2. Check whether CI actually caught it: get_github_runs / get_azure_devops_
   builds(failed_only=true). A dependency break sometimes only manifests at
   runtime under production load/config/environment that CI doesn't
   replicate, so a green CI run doesn't rule this out.
3. search_logs/query_azure_logs/query_aws_logs for an import/load error
   immediately at process startup, not mid-request — the specific string
   differs by ecosystem, but the shape (crash before the app is even
   serving traffic) is the same regardless of language.
4. Confirm it's the dependency, not application code: reverting only the
   manifest/lockfile (not app code) should resolve it if this runbook
   applies.

## Fix
Pin/rollback the dependency to the last known-good version; add a
startup/smoke test to CI that actually exercises the changed import path,
since version bumps routinely pass a test suite that never touches the
affected code.
