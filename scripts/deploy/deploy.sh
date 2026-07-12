#!/usr/bin/env bash
# Deploys/redeploys PhantomInvestigator on a plain Docker Compose host --
# the underlying command a Coolify/Dokku resource would also run, if this
# server turns out to be running one of those instead (see docs/deployment.md
# step 0). agent/ is baked into the image, not volume-mounted (see
# CLAUDE.md's gotcha), so a real rebuild is required on every deploy, not
# just a restart.
set -euo pipefail
cd "$(dirname "$0")/../.."

if [ ! -f .env ]; then
  echo "error: .env not found -- copy .env.example, fill in the checklist in docs/deployment.md, then re-run" >&2
  exit 1
fi

git pull --ff-only
docker compose -f docker-compose.prod.yml up -d --build

echo "Waiting for the agent healthcheck..."
for _ in $(seq 1 30); do
  status="$(docker inspect --format '{{.State.Health.Status}}' phantom-investigator-agent-1 2>/dev/null || echo unknown)"
  [ "$status" = "healthy" ] && { echo "agent is healthy."; exit 0; }
  sleep 2
done

echo "error: agent did not become healthy in time -- check 'docker compose -f docker-compose.prod.yml logs agent'" >&2
exit 1
