#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

env_get() {
  local key="$1"
  local line
  line="$(grep -E "^[[:space:]]*${key}=" "$ENV_FILE" | tail -n1 || true)"
  line="${line#*=}"
  line="${line%$'\r'}"
  printf '%s' "$line"
}

valid_domain() {
  local domain="$1"
  [[ "$domain" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$ ]]
}

valid_email() {
  local email="$1"
  [[ "$email" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]
}

NGINX_SERVER_NAME="${NGINX_SERVER_NAME:-$(env_get NGINX_SERVER_NAME)}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-$(env_get CERTBOT_EMAIL)}"

: "${NGINX_SERVER_NAME:?NGINX_SERVER_NAME is required in .env}"
: "${CERTBOT_EMAIL:?CERTBOT_EMAIL is required in .env}"

if ! valid_domain "$NGINX_SERVER_NAME"; then
  echo "NGINX_SERVER_NAME must be a public DNS name, got: $NGINX_SERVER_NAME" >&2
  exit 1
fi

if ! valid_email "$CERTBOT_EMAIL"; then
  echo "CERTBOT_EMAIL must be a valid email address, got: $CERTBOT_EMAIL" >&2
  exit 1
fi

docker compose \
  -f "$REPO_ROOT/deploy/infra/docker-compose.yml" \
  --env-file "$ENV_FILE" \
  run --rm --entrypoint certbot certbot certonly \
  --webroot \
  -w /var/www/certbot \
  -d "$NGINX_SERVER_NAME" \
  --email "$CERTBOT_EMAIL" \
  --non-interactive \
  --quiet \
  --agree-tos \
  --no-eff-email
