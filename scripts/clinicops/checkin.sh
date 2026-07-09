#!/usr/bin/env bash
# Runs ON the ClinicOps server (or as the last step of its deploy workflow).
# Reports this deployment's current version/build to PhantomInvestigator's
# check-in webhook (agent/routes/checkin.py) so drift detection has a real
# signal instead of treating the deployment as black-box.
set -euo pipefail

: "${PHANTOM_BASE_URL:?set to the PhantomInvestigator public URL, e.g. https://xxxx.ngrok-free.app}"
: "${DEPLOYMENT_ID:?set to this deployment id, from /clients}"
: "${CHECKIN_SECRET:?set to this deployment checkin_token, from /clients}"

# Prefer explicit values (e.g. set by the deploy workflow from the commit
# that's actually being deployed); fall back to reading git state if this
# script is run from within a checkout.
VERSION="${CLINICOPS_VERSION:-$(git describe --tags --always 2>/dev/null || echo unknown)}"
BUILD_SHA="${CLINICOPS_BUILD_SHA:-$(git rev-parse HEAD 2>/dev/null || echo unknown)}"

curl -sf -X POST \
  "${PHANTOM_BASE_URL%/}/webhooks/checkin/${DEPLOYMENT_ID}?secret=${CHECKIN_SECRET}" \
  -H 'Content-Type: application/json' \
  -d "{\"version\": \"${VERSION}\", \"build_sha\": \"${BUILD_SHA}\"}" \
  -o /dev/null

echo "Checked in: version=${VERSION} build_sha=${BUILD_SHA}"
