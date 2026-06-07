#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"

DOMAIN=""
EMAIL=""
STOP_HOST_NGINX=false
REMOVE_OPEN_WEBUI_TEST_STACK=false
SKIP_BUILD=false
SKIP_SMOKE=false

usage() {
  cat <<'EOF'
Usage:
  bash deploy/server/deploy.sh --domain example.com --email admin@example.com [options]

Options:
  --domain <domain>                    Public domain for the app.
  --email <email>                     Email for Let's Encrypt and Directus admin default.
  --env-file <path>                   Override .env path. Default: repo root .env
  --stop-host-nginx                   Stop and disable system nginx before deployment.
  --remove-open-webui-test-stack      Remove the test ollama/open-webui stack if present.
  --skip-build                        Reuse existing images for the app stack.
  --skip-smoke                        Skip post-deploy HTTP smoke checks.
EOF
}

valid_domain() {
  local domain="$1"
  [[ "$domain" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$ ]]
}

valid_email() {
  local email="$1"
  [[ "$email" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]
}

validate_deploy_inputs() {
  if [[ -n "$DOMAIN" ]] && ! valid_domain "$DOMAIN"; then
    echo "--domain must be a public DNS name, got: $DOMAIN" >&2
    exit 1
  fi

  if [[ -n "$EMAIL" ]] && ! valid_email "$EMAIL"; then
    echo "--email must be a valid email address, got: $EMAIL" >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN="${2:-}"
      shift 2
      ;;
    --email)
      EMAIL="${2:-}"
      shift 2
      ;;
    --env-file)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --stop-host-nginx)
      STOP_HOST_NGINX=true
      shift
      ;;
    --remove-open-webui-test-stack)
      REMOVE_OPEN_WEBUI_TEST_STACK=true
      shift
      ;;
    --skip-build)
      SKIP_BUILD=true
      shift
      ;;
    --skip-smoke)
      SKIP_SMOKE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

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

  echo "Docker is not available for the current user. Run bootstrap-ubuntu.sh first." >&2
  exit 1
}

compose() {
  "${DOCKER_CMD[@]}" compose "$@"
}

env_get() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true
}

escape_sed_replacement() {
  printf '%s' "$1" | sed -e 's/[\/&|]/\\&/g'
}

env_set() {
  local key="$1"
  local value="$2"
  local escaped
  escaped="$(escape_sed_replacement "$value")"

  if grep -qE "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${escaped}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

ensure_env_file() {
  if [[ ! -f "$ENV_FILE" ]]; then
    cp "$REPO_ROOT/.env.example" "$ENV_FILE"
  fi
}

generate_secret() {
  openssl rand -hex 32
}

ensure_random_secret() {
  local key="$1"
  local current
  current="$(env_get "$key" || true)"

  if [[ -z "$current" || "$current" == change-me-* || "$current" == replace-with-* ]]; then
    env_set "$key" "$(generate_secret)"
  fi
}

update_domain_derived_env() {
  if [[ -n "$DOMAIN" ]]; then
    env_set "NGINX_SERVER_NAME" "$DOMAIN"
    env_set "APP_BASE_URL" "https://$DOMAIN"
    env_set "DIRECTUS_PUBLIC_URL" "https://$DOMAIN/directus"
    env_set "DIRECTUS_ADMIN_EMAIL" "admin@$DOMAIN"
    env_set "DEFAULT_FROM_EMAIL" "no-reply@$DOMAIN"
    if [[ -z "$(env_get "ALLOWED_HOSTS" || true)" ]]; then
      env_set "ALLOWED_HOSTS" "127.0.0.1,localhost,$DOMAIN,backend,jupyterhub,directus,nginx"
    fi
    if [[ -z "$(env_get "TRAINING_JUPYTERHUB_BASE_URL" || true)" ]]; then
      env_set "TRAINING_JUPYTERHUB_BASE_URL" "https://$DOMAIN/lab"
    fi
  fi

  if [[ -n "$EMAIL" ]]; then
    env_set "CERTBOT_EMAIL" "$EMAIL"
  fi

  if [[ -z "$(env_get "DIRECTUS_HTTP_BIND" || true)" ]]; then
    env_set "DIRECTUS_HTTP_BIND" "127.0.0.1"
  fi
  if [[ -z "$(env_get "MAILPIT_HTTP_BIND" || true)" ]]; then
    env_set "MAILPIT_HTTP_BIND" "127.0.0.1"
  fi
  if [[ -z "$(env_get "MAILPIT_HTTP_PORT" || true)" ]]; then
    env_set "MAILPIT_HTTP_PORT" "8025"
  fi
  if [[ -z "$(env_get "DIRECTUS_EMAIL_TRANSPORT" || true)" ]]; then
    env_set "DIRECTUS_EMAIL_TRANSPORT" "smtp"
  fi
  if [[ -z "$(env_get "DIRECTUS_EMAIL_FROM" || true)" ]]; then
    env_set "DIRECTUS_EMAIL_FROM" "$(env_get "DEFAULT_FROM_EMAIL" || true)"
  fi
  if [[ -z "$(env_get "DIRECTUS_EMAIL_FROM_NAME" || true)" ]]; then
    env_set "DIRECTUS_EMAIL_FROM_NAME" "OnlineLessons"
  fi
  if [[ -z "$(env_get "DIRECTUS_EMAIL_SMTP_HOST" || true)" ]]; then
    env_set "DIRECTUS_EMAIL_SMTP_HOST" "mailpit"
  fi
  if [[ -z "$(env_get "DIRECTUS_EMAIL_SMTP_PORT" || true)" ]]; then
    env_set "DIRECTUS_EMAIL_SMTP_PORT" "1025"
  fi
  if [[ -z "$(env_get "DIRECTUS_EMAIL_SMTP_SECURE" || true)" ]]; then
    env_set "DIRECTUS_EMAIL_SMTP_SECURE" "false"
  fi
  if [[ -z "$(env_get "DIRECTUS_EMAIL_VERIFY_SETUP" || true)" ]]; then
    env_set "DIRECTUS_EMAIL_VERIFY_SETUP" "false"
  fi
  if [[ -z "$(env_get "TRAINING_NBGRADER_COURSE_ROOT" || true)" ]]; then
    env_set "TRAINING_NBGRADER_COURSE_ROOT" "/app/media/training/nbgrader-course"
  fi

  if git -C "$REPO_ROOT" rev-parse --short HEAD >/dev/null 2>&1; then
    env_set "APP_RELEASE" "$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
  fi

  ensure_random_secret "POSTGRES_SUPERPASSWORD"
  ensure_random_secret "APP_DB_PASSWORD"
  ensure_random_secret "DIRECTUS_DB_PASSWORD"
  ensure_random_secret "DJANGO_SECRET_KEY"
  ensure_random_secret "DIRECTUS_KEY"
  ensure_random_secret "DIRECTUS_SECRET"
  ensure_random_secret "DIRECTUS_ADMIN_PASSWORD"
  ensure_random_secret "TRAINING_JUPYTERHUB_SERVICE_TOKEN"
  ensure_random_secret "TRAINING_JUPYTERHUB_API_TOKEN"
  ensure_random_secret "TRAINING_JUPYTERHUB_SHARED_SECRET"
  ensure_random_secret "TRAINING_GRADER_WEBHOOK_SECRET"
  ensure_random_secret "TRAINING_DIRECTUS_SYNC_TOKEN"
  ensure_random_secret "JUPYTERHUB_CRYPT_KEY"
}

ensure_runtime_resources() {
  "${DOCKER_CMD[@]}" volume create jupyterhub_data >/dev/null
}

current_domain() {
  local domain
  domain="$(env_get "NGINX_SERVER_NAME" || true)"
  if [[ -z "$domain" ]]; then
    echo "NGINX_SERVER_NAME is not set in $ENV_FILE" >&2
    exit 1
  fi
  printf '%s' "$domain"
}

current_email() {
  local email
  email="$(env_get "CERTBOT_EMAIL" || true)"
  if [[ -z "$email" ]]; then
    echo "CERTBOT_EMAIL is not set in $ENV_FILE" >&2
    exit 1
  fi
  printf '%s' "$email"
}

warn_dns_if_needed() {
  local domain="$1"
  local current_ip dns_ip

  current_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  dns_ip="$(getent ahostsv4 "$domain" 2>/dev/null | awk 'NR==1 {print $1}')"

  if [[ -z "$dns_ip" ]]; then
    echo "Warning: DNS for $domain is not resolving yet from this server."
    return
  fi

  if [[ -n "$current_ip" && "$current_ip" != "$dns_ip" ]]; then
    echo "Warning: $domain resolves to $dns_ip, while this server reports $current_ip."
  fi
}

backup_and_stop_host_nginx() {
  if ! command -v systemctl >/dev/null 2>&1; then
    return
  fi

  if ! systemctl is-active --quiet nginx; then
    return
  fi

  if [[ "$STOP_HOST_NGINX" != "true" ]]; then
    echo "Port 80/443 are occupied by system nginx. Re-run with --stop-host-nginx to reclaim them." >&2
    exit 1
  fi

  local backup_dir
  backup_dir="/etc/nginx/backup-learning-hub-$(date +%Y%m%d-%H%M%S)"
  sudo mkdir -p "$backup_dir"
  sudo cp -a /etc/nginx/sites-available "$backup_dir/" 2>/dev/null || true
  sudo cp -a /etc/nginx/sites-enabled "$backup_dir/" 2>/dev/null || true
  sudo systemctl stop nginx
  sudo systemctl disable nginx || true
}

remove_open_webui_test_stack() {
  if [[ "$REMOVE_OPEN_WEBUI_TEST_STACK" != "true" ]]; then
    return
  fi

  local stack_dir
  stack_dir="$HOME/projects/ollama"

  if [[ -f "$stack_dir/docker-compose.yml" ]]; then
    compose -f "$stack_dir/docker-compose.yml" down --remove-orphans || true
  fi

  "${DOCKER_CMD[@]}" rm -f open-webui ollama >/dev/null 2>&1 || true
}

require_free_http_ports() {
  if compose -f "$REPO_ROOT/deploy/infra/docker-compose.yml" --env-file "$ENV_FILE" ps -q nginx 2>/dev/null | grep -q .; then
    return
  fi

  local listeners
  listeners="$(ss -tulpn | grep -E '(:80 |:443 )' || true)"

  if [[ -n "$listeners" ]]; then
    echo "$listeners"
    echo "Ports 80/443 are still busy. Free them before deploying the self-contained nginx stack." >&2
    exit 1
  fi
}

start_infra_http() {
  compose -f "$REPO_ROOT/deploy/infra/docker-compose.yml" --env-file "$ENV_FILE" up -d
}

issue_initial_certificate_if_needed() {
  local domain="$1"
  local cert_path
  cert_path="$REPO_ROOT/deploy/infra/certbot/conf/live/$domain/fullchain.pem"

  if [[ -f "$cert_path" ]]; then
    echo "Certificate already present for $domain"
    return
  fi

  ENV_FILE="$ENV_FILE" bash "$REPO_ROOT/deploy/infra/certbot/issue-initial-cert.sh"
}

start_infra_tls() {
  compose \
    -f "$REPO_ROOT/deploy/infra/docker-compose.yml" \
    -f "$REPO_ROOT/deploy/infra/docker-compose.tls.yml" \
    --env-file "$ENV_FILE" \
    up -d
}

ensure_app_database_extensions() {
  compose \
    -f "$REPO_ROOT/deploy/infra/docker-compose.yml" \
    --env-file "$ENV_FILE" \
    exec -T database sh -lc '
      PGPASSWORD="$POSTGRES_PASSWORD" \
      psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$APP_DB_NAME" -v ON_ERROR_STOP=1 \
      -c "CREATE EXTENSION IF NOT EXISTS vector"
    '
}

start_app_stack() {
  if [[ "$SKIP_BUILD" == "true" ]]; then
    compose -f "$REPO_ROOT/deploy/app/docker-compose.yml" --env-file "$ENV_FILE" up -d
    return
  fi

  compose -f "$REPO_ROOT/deploy/app/docker-compose.yml" --env-file "$ENV_FILE" up --build -d
}

provision_directus_flows() {
  python3 "$REPO_ROOT/deploy/directus/setup_training_directus.py" --env-file "$ENV_FILE"
  python3 "$REPO_ROOT/deploy/directus/setup_directus_communications.py" --env-file "$ENV_FILE" --write-env
  compose -f "$REPO_ROOT/deploy/app/docker-compose.yml" --env-file "$ENV_FILE" up -d --force-recreate backend scheduler traininggrader
}

show_status() {
  echo
  echo "Infra status:"
  compose -f "$REPO_ROOT/deploy/infra/docker-compose.yml" --env-file "$ENV_FILE" ps
  echo
  echo "App status:"
  compose -f "$REPO_ROOT/deploy/app/docker-compose.yml" --env-file "$ENV_FILE" ps
  echo
  echo "Public URL: https://$(current_domain)"
  echo "Student:    https://$(current_domain)/student/"
  echo "Teacher:    https://$(current_domain)/teacher/"
  echo "Admin:      https://$(current_domain)/office/"
  echo "Directus:   https://$(current_domain)/directus/"
}

run_smoke_test() {
  local domain
  domain="$(current_domain)"

  if [[ "$SKIP_SMOKE" == "true" ]]; then
    echo "Skipping smoke test."
    return
  fi

  ENV_FILE="$ENV_FILE" bash "$REPO_ROOT/deploy/server/smoke-test.sh" --domain "$domain"
}

main() {
  validate_deploy_inputs
  pick_docker_cmd
  ensure_env_file
  update_domain_derived_env

  local domain email
  domain="$(current_domain)"
  email="$(current_email)"
  warn_dns_if_needed "$domain"

  echo "Using domain: $domain"
  echo "Using certbot email: $email"

  backup_and_stop_host_nginx
  remove_open_webui_test_stack
  require_free_http_ports
  ensure_runtime_resources
  start_infra_http
  issue_initial_certificate_if_needed "$domain"
  start_infra_tls
  ensure_app_database_extensions
  start_app_stack
  provision_directus_flows
  run_smoke_test
  show_status
}

main
