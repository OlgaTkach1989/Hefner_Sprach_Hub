#!/usr/bin/env bash
set -euo pipefail

BEGIN_MARK="# BEGIN studentlist-online-scheduler"
END_MARK="# END studentlist-online-scheduler"

CURRENT_CRON="$(crontab -l 2>/dev/null || true)"
NEW_CRON="$(printf "%s\n" "${CURRENT_CRON}" | sed "/^${BEGIN_MARK}$/,/^${END_MARK}$/d")"

printf "%s\n" "${NEW_CRON}" | crontab -
echo "Removed managed online scheduler cron block for user: $(whoami)"
