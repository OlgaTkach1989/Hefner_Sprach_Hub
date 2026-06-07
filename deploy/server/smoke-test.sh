#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/server/common.sh
source "$SCRIPT_DIR/common.sh"

DOMAIN=""
TIMEOUT_SECONDS=180
SKIP_DIRECTUS=false
SKIP_LAB=false
ALLOW_INSECURE_TLS=false

usage() {
  cat <<'EOF'
Usage:
  bash deploy/server/smoke-test.sh [options]

Options:
  --domain <domain>         Override domain from .env
  --env-file <path>         Override env file
  --timeout <seconds>       Total wait time per endpoint. Default: 180
  --skip-directus           Skip Directus route verification
  --skip-lab                Skip /lab/ verification
  --insecure                Allow insecure TLS for curl
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN="${2:-}"
      shift 2
      ;;
    --env-file)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --timeout)
      TIMEOUT_SECONDS="${2:-180}"
      shift 2
      ;;
    --skip-directus)
      SKIP_DIRECTUS=true
      shift
      ;;
    --skip-lab)
      SKIP_LAB=true
      shift
      ;;
    --insecure)
      ALLOW_INSECURE_TLS=true
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

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

if [[ -z "$DOMAIN" ]]; then
  DOMAIN="$(current_domain)"
fi

BASE_URL="$(current_app_base_url)"
if [[ "$BASE_URL" != *"$DOMAIN"* ]]; then
  BASE_URL="https://$DOMAIN"
fi

CURL_FLAGS=(-sS -L --max-time 15)
PYTHON_CMD="$(command -v python3 || command -v python || true)"
if [[ "$ALLOW_INSECURE_TLS" == "true" ]]; then
  CURL_FLAGS+=(-k)
fi

HAS_DOCKER=false
if pick_docker_cmd >/dev/null 2>&1; then
  HAS_DOCKER=true
fi

wait_for_url() {
  local label="$1"
  local url="$2"
  local expected_mode="${3:-ok}"
  local start_ts now http_code tmp_body

  start_ts="$(date +%s)"
  tmp_body="$(mktemp)"
  trap 'rm -f "$tmp_body"' RETURN

  while true; do
    http_code="$(curl "${CURL_FLAGS[@]}" -o "$tmp_body" -w "%{http_code}" "$url" || true)"
    if [[ "$expected_mode" == "protected_route" ]]; then
      if [[ "$http_code" =~ ^2[0-9][0-9]$ || "$http_code" =~ ^3[0-9][0-9]$ || "$http_code" == "403" || "$http_code" == "405" ]]; then
        echo "[OK] $label -> $url"
        break
      fi
    elif [[ "$http_code" =~ ^2[0-9][0-9]$ ]]; then
      if [[ "$expected_mode" == "ready_json" ]]; then
        if [[ -z "$PYTHON_CMD" ]]; then
          echo "[FAIL] $label -> $url (python3/python is required for ready_json checks)" >&2
          return 1
        fi
        if "$PYTHON_CMD" - "$tmp_body" <<'PY'
import json
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
if payload.get("ready") is True and payload.get("status") == "ok":
    raise SystemExit(0)
raise SystemExit(1)
PY
        then
          echo "[OK] $label -> $url"
          break
        fi
      else
        echo "[OK] $label -> $url"
        break
      fi
    fi

    now="$(date +%s)"
    if (( now - start_ts >= TIMEOUT_SECONDS )); then
      echo "[FAIL] $label -> $url (last HTTP code: ${http_code:-none})" >&2
      if [[ -s "$tmp_body" ]]; then
        echo "--- response body ---" >&2
        cat "$tmp_body" >&2 || true
        echo >&2
      fi
      exit 1
    fi
    sleep 5
  done
}

if [[ "$HAS_DOCKER" == "true" ]]; then
  echo "Infra services:"
  compose_infra ps || true
  echo
  echo "App services:"
  compose_app ps || true
  echo
fi

wait_for_url "API liveness" "$BASE_URL/api/health/"
wait_for_url "API readiness" "$BASE_URL/api/health/ready/" "ready_json"
wait_for_url "Nginx healthz" "$BASE_URL/healthz" "ready_json"
wait_for_url "Public app" "$BASE_URL/"
wait_for_url "Student app" "$BASE_URL/student/"
wait_for_url "Teacher app" "$BASE_URL/teacher/"
wait_for_url "Admin app" "$BASE_URL/office/"

if [[ "$SKIP_DIRECTUS" != "true" ]]; then
  wait_for_url "Directus route" "$BASE_URL/directus/"
fi

if [[ "$SKIP_LAB" != "true" ]] && [[ "$(env_get "TRAINING_NOTEBOOK_RUNTIME_ENABLED" || true)" == "true" ]]; then
  wait_for_url "JupyterHub route" "$BASE_URL/lab/" "protected_route"
fi

echo
echo "Smoke test passed for $BASE_URL"
