#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR_DEFAULT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
PROJECT_DIR="${PROJECT_DIR:-${PROJECT_DIR_DEFAULT}}"
LOG_DIR="${ONLINE_SCHEDULER_LOG_DIR:-${PROJECT_DIR}/logs/scheduler}"

REMINDER_SCHEDULE="${ONLINE_REMINDER_CRON:-*/10 * * * *}"
ATTENDANCE_SCHEDULE="${ONLINE_ATTENDANCE_CRON:-5-59/10 * * * *}"

BEGIN_MARK="# BEGIN studentlist-online-scheduler"
END_MARK="# END studentlist-online-scheduler"

FLOCK_BIN="$(command -v flock || true)"
if [[ -z "${FLOCK_BIN}" ]]; then
  echo "flock is not installed. Install util-linux and re-run."
  exit 1
fi

if ! command -v crontab >/dev/null 2>&1; then
  echo "crontab is not installed. Install cron package and re-run."
  exit 1
fi

mkdir -p "${LOG_DIR}"

REMINDER_SCRIPT="${PROJECT_DIR}/scripts/online_scheduler/run_online_reminders.sh"
ATTENDANCE_SCRIPT="${PROJECT_DIR}/scripts/online_scheduler/run_online_attendance_sync.sh"

if [[ ! -f "${REMINDER_SCRIPT}" || ! -f "${ATTENDANCE_SCRIPT}" ]]; then
  echo "Scheduler scripts not found in ${PROJECT_DIR}/scripts/online_scheduler"
  exit 1
fi

chmod +x "${REMINDER_SCRIPT}" "${ATTENDANCE_SCRIPT}"

CURRENT_CRON="$(crontab -l 2>/dev/null || true)"
CLEAN_CRON="$(printf "%s\n" "${CURRENT_CRON}" | sed "/^${BEGIN_MARK}$/,/^${END_MARK}$/d")"

CRON_BLOCK="$(cat <<EOF
${BEGIN_MARK}
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
${REMINDER_SCHEDULE} ${FLOCK_BIN} -n /tmp/studentlist-online-reminders.lock '${REMINDER_SCRIPT}' >> '${LOG_DIR}/online_reminders.log' 2>&1
${ATTENDANCE_SCHEDULE} ${FLOCK_BIN} -n /tmp/studentlist-online-attendance.lock '${ATTENDANCE_SCRIPT}' >> '${LOG_DIR}/online_attendance_sync.log' 2>&1
${END_MARK}
EOF
)"

{
  printf "%s\n" "${CLEAN_CRON}"
  printf "%s\n" "${CRON_BLOCK}"
} | crontab -

echo "Installed online scheduler cron jobs for user: $(whoami)"
echo "Log dir: ${LOG_DIR}"
echo "Current managed block:"
crontab -l | sed -n "/^${BEGIN_MARK}$/,/^${END_MARK}$/p"
