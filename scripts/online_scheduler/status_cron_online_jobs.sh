#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR_DEFAULT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
PROJECT_DIR="${PROJECT_DIR:-${PROJECT_DIR_DEFAULT}}"
LOG_DIR="${ONLINE_SCHEDULER_LOG_DIR:-${PROJECT_DIR}/logs/scheduler}"

BEGIN_MARK="# BEGIN studentlist-online-scheduler"
END_MARK="# END studentlist-online-scheduler"

echo "Managed cron block (user: $(whoami)):"
crontab -l 2>/dev/null | sed -n "/^${BEGIN_MARK}$/,/^${END_MARK}$/p" || true

echo
echo "Recent logs:"
if [[ -f "${LOG_DIR}/online_reminders.log" ]]; then
  echo "--- ${LOG_DIR}/online_reminders.log (last 20 lines) ---"
  tail -n 20 "${LOG_DIR}/online_reminders.log"
else
  echo "No reminders log yet: ${LOG_DIR}/online_reminders.log"
fi

echo
if [[ -f "${LOG_DIR}/online_attendance_sync.log" ]]; then
  echo "--- ${LOG_DIR}/online_attendance_sync.log (last 20 lines) ---"
  tail -n 20 "${LOG_DIR}/online_attendance_sync.log"
else
  echo "No attendance log yet: ${LOG_DIR}/online_attendance_sync.log"
fi
