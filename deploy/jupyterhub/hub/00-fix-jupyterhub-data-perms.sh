#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" != "0" ]; then
  return 0 2>/dev/null || exit 0
fi

mkdir -p /data
chown -R "${NB_UID}:${NB_GID}" /data
