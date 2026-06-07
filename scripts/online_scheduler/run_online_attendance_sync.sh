#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR_DEFAULT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
PROJECT_DIR="${PROJECT_DIR:-${PROJECT_DIR_DEFAULT}}"

LOOKBACK_HOURS="${ONLINE_ATTENDANCE_LOOKBACK_HOURS:-48}"
RETRY_MINUTES="${ONLINE_ATTENDANCE_RETRY_MINUTES:-30}"
LIMIT="${ONLINE_ATTENDANCE_BATCH_LIMIT:-100}"

cd "${PROJECT_DIR}"
echo "[$(date --iso-8601=seconds)] online attendance sync started (lookback=${LOOKBACK_HOURS}h, retry=${RETRY_MINUTES}m, limit=${LIMIT})"
docker compose exec -T backend python manage.py sync_online_attendance_batch \
  --lookback-hours "${LOOKBACK_HOURS}" \
  --retry-minutes "${RETRY_MINUTES}" \
  --limit "${LIMIT}"
echo "[$(date --iso-8601=seconds)] online attendance sync finished"
