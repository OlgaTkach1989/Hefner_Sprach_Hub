#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR_DEFAULT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
PROJECT_DIR="${PROJECT_DIR:-${PROJECT_DIR_DEFAULT}}"

REMINDER_HOURS="${ONLINE_REMINDER_HOURS:-24,1}"
WINDOW_MINUTES="${ONLINE_REMINDER_WINDOW_MINUTES:-10}"

cd "${PROJECT_DIR}"
echo "[$(date --iso-8601=seconds)] online reminders started (hours=${REMINDER_HOURS}, window=${WINDOW_MINUTES})"
docker compose exec -T backend python manage.py send_online_session_reminders \
  --hours "${REMINDER_HOURS}" \
  --window-minutes "${WINDOW_MINUTES}"
echo "[$(date --iso-8601=seconds)] online reminders finished"
