#!/usr/bin/env bash
# Configures a reverse proxy + TLS for PhantomInvestigator on the ClinicOps
# VPS. Confirmed (via ClinicOps's own repo: docs/github-secrets.md,
# docker-compose.yml, Makefile) that this server runs plain Docker Compose,
# SSH-deployed -- no Coolify, no Dokku. What's still unknown from here is
# only which reverse proxy (if any) is already fronting ClinicOps, so this
# detects nginx vs Caddy vs neither instead of requiring a manual check.
#
# Usage: sudo scripts/deploy/setup-proxy.sh [domain] [upstream]
set -euo pipefail

DOMAIN="${1:-phantominvestigator.com}"
UPSTREAM="${2:-localhost:8085}"

if systemctl is-active --quiet nginx 2>/dev/null; then
  echo "nginx is already running -- adding a server block for ${DOMAIN}."
  cat > "/etc/nginx/sites-available/${DOMAIN}" <<NGINX
server {
    listen 80;
    server_name ${DOMAIN};
    location / {
        proxy_pass http://${UPSTREAM};
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
NGINX
  ln -sf "/etc/nginx/sites-available/${DOMAIN}" "/etc/nginx/sites-enabled/${DOMAIN}"
  nginx -t
  systemctl reload nginx
  echo "nginx configured for plain HTTP. Add TLS with: sudo certbot --nginx -d ${DOMAIN}"

elif systemctl is-active --quiet caddy 2>/dev/null || command -v caddy >/dev/null 2>&1; then
  echo "Caddy is already present -- appending a site block (automatic TLS, no certbot needed)."
  CADDYFILE="/etc/caddy/Caddyfile"
  if ! grep -q "^${DOMAIN} " "$CADDYFILE" 2>/dev/null; then
    printf '\n%s {\n\treverse_proxy %s\n}\n' "$DOMAIN" "$UPSTREAM" >> "$CADDYFILE"
  fi
  systemctl reload caddy

else
  echo "Neither nginx nor Caddy found running -- installing Caddy (automatic TLS, simplest for a fresh domain)."
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq
    apt-get install -y -qq caddy
  else
    echo "error: apt-get not found -- install Caddy manually: https://caddyserver.com/docs/install" >&2
    exit 1
  fi
  cp "$(dirname "$0")/Caddyfile.example" /etc/caddy/Caddyfile
  sed -i "s/phantominvestigator\.com/${DOMAIN}/; s#localhost:8085#${UPSTREAM}#" /etc/caddy/Caddyfile
  systemctl enable --now caddy
fi

echo "Done. Once DNS for ${DOMAIN} points at this host, verify with: curl -I https://${DOMAIN}/health"
