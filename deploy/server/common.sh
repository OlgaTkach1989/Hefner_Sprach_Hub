#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

pick_docker_cmd() {
  if need_cmd docker && docker info >/dev/null 2>&1; then
    DOCKER_CMD=(docker)
    return
  fi

  if need_cmd sudo && sudo docker info >/dev/null 2>&1; then
    DOCKER_CMD=(sudo docker)
    return
  fi

  echo "Docker is not available for the current user." >&2
  return 1
}

compose_infra() {
  "${DOCKER_CMD[@]}" compose -f "$REPO_ROOT/deploy/infra/docker-compose.yml" --env-file "$ENV_FILE" "$@"
}

compose_app() {
  "${DOCKER_CMD[@]}" compose -f "$REPO_ROOT/deploy/app/docker-compose.yml" --env-file "$ENV_FILE" "$@"
}

env_get() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true
}

current_domain() {
  local domain
  domain="$(env_get "NGINX_SERVER_NAME" || true)"
  if [[ -z "$domain" ]]; then
    echo "NGINX_SERVER_NAME is not set in $ENV_FILE" >&2
    return 1
  fi
  printf '%s' "$domain"
}

current_app_base_url() {
  local app_base_url
  app_base_url="$(env_get "APP_BASE_URL" || true)"
  if [[ -n "$app_base_url" ]]; then
    printf '%s' "$app_base_url"
    return
  fi
  printf 'https://%s' "$(current_domain)"
}
