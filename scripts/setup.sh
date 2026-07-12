#!/usr/bin/env bash
# Interactive bootstrap: .env.example -> .env with every generatable secret
# filled in automatically, so a new user only answers a handful of questions
# instead of reading 40 lines of comments and running openssl by hand.
set -euo pipefail
cd "$(dirname "$0")/.."

ENV_FILE=.env
ENV_EXAMPLE=.env.example

if [ ! -f "$ENV_EXAMPLE" ]; then
  echo "error: $ENV_EXAMPLE not found (run this from the repo root)" >&2
  exit 1
fi

if [ -f "$ENV_FILE" ]; then
  read -rp ".env already exists. Overwrite blank/placeholder values only, keeping anything you've already filled in? [Y/n] " keep
  if [[ "$keep" =~ ^[Nn] ]]; then
    echo "Leaving .env untouched."
    exit 0
  fi
else
  cp "$ENV_EXAMPLE" "$ENV_FILE"
fi

rand_hex() { openssl rand -hex "$1"; }
rand_fernet() { openssl rand -base64 32 | tr '+/' '-_'; }

# current value of VAR in .env, with any inline "# comment" and surrounding
# whitespace stripped -- so a blank value followed by a comment (e.g.
# "EMBEDDING_API_KEY=    # your key here") still reads as blank
current_value() {
  grep -E "^${1}=" "$ENV_FILE" | head -1 | sed -E "s/^${1}=//; s/[[:space:]]+#.*$//; s/[[:space:]]+$//"
}

# true if VAR is unset, blank, or still holds a "..." placeholder like sk-ant-...
is_blank() {
  local val
  val="$(current_value "$1")"
  [ -z "$val" ] || [[ "$val" == *"..." ]]
}

# set VAR to VALUE only if VAR is currently unset/blank/placeholder in .env
fill() {
  local var="$1" value="$2"
  is_blank "$var" || return 0
  if grep -qE "^${var}=" "$ENV_FILE"; then
    # portable in-place edit (works with both GNU and BSD sed)
    sed -i.bak "s#^${var}=.*#${var}=${value}#" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
  else
    echo "${var}=${value}" >> "$ENV_FILE"
  fi
}

echo "Generating secrets that don't need a human to invent them..."

fill SESSION_SECRET "$(rand_hex 32)"
fill CREDENTIALS_ENCRYPTION_KEY "$(rand_fernet)"
fill POSTGRES_PASSWORD "$(rand_hex 16)"

# DATABASE_URL's password can't reference ${POSTGRES_PASSWORD} -- env_file:
# doesn't expand vars inside another var's value -- so keep them in sync here.
PG_PASSWORD="$(current_value POSTGRES_PASSWORD)"
sed -i.bak -E "s#(^DATABASE_URL=postgresql://postgres:)[^@]*(@.*)#\1${PG_PASSWORD}\2#" "$ENV_FILE" && rm -f "$ENV_FILE.bak"

fill LANGFUSE_SALT "$(rand_hex 32)"
fill LANGFUSE_ENCRYPTION_KEY "$(rand_hex 32)"
fill LANGFUSE_NEXTAUTH_SECRET "$(rand_hex 32)"
fill LANGFUSE_POSTGRES_PASSWORD "$(rand_hex 16)"
fill LANGFUSE_CLICKHOUSE_PASSWORD "$(rand_hex 16)"
fill LANGFUSE_REDIS_AUTH "$(rand_hex 16)"
fill LANGFUSE_MINIO_ROOT_PASSWORD "$(rand_hex 16)"
fill LANGFUSE_INIT_USER_PASSWORD "$(rand_hex 12)"

# public/secret key pair must match between the agent's LANGFUSE_* client
# vars and the LANGFUSE_INIT_PROJECT_* vars langfuse-web provisions from
LF_PUBLIC="pk-lf-$(rand_hex 16)"
LF_SECRET="sk-lf-$(rand_hex 16)"
fill LANGFUSE_INIT_PROJECT_PUBLIC_KEY "$LF_PUBLIC"
fill LANGFUSE_INIT_PROJECT_SECRET_KEY "$LF_SECRET"
fill LANGFUSE_PUBLIC_KEY "$LF_PUBLIC"
fill LANGFUSE_SECRET_KEY "$LF_SECRET"
fill LANGFUSE_INIT_ORG_ID "org-$(rand_hex 8)"
fill LANGFUSE_INIT_PROJECT_ID "proj-$(rand_hex 8)"

echo
echo "A few things nobody but you can provide -- leave blank to skip and fill in later:"

ask() {
  local var="$1" prompt="$2"
  is_blank "$var" || return 0 # already set (e.g. re-running setup) -- don't ask again
  read -rp "$prompt: " value
  [ -n "$value" ] && fill "$var" "$value"
}

ask ANTHROPIC_API_KEY "Anthropic API key, https://console.anthropic.com (powers the agent loop)"
ask EMBEDDING_API_KEY "Voyage AI key, https://dash.voyageai.com (powers runbook search -- account creation still works without it)"

echo
echo "Done. Core config + Langfuse are ready for 'make up'."
echo "Jira/GitHub/Azure/AWS integrations are still blank -- wire them up later from"
echo "the Integrations page after you register, or by editing .env directly."
