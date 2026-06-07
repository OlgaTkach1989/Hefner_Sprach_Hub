#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/server/common.sh
source "$SCRIPT_DIR/common.sh"

TARGET_DB_KIND=""
BACKUP_FILE=""
RESET_DB=true

usage() {
  cat <<'EOF'
Usage:
  bash deploy/server/restore-postgres.sh --db app --backup-file /path/to/online_lessons.sql.gz [options]

Options:
  --env-file <path>         Override env file
  --db <app|directus>       Target database preset
  --backup-file <path>      SQL or SQL.GZ dump file
  --no-reset                Import without dropping the public schema first
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --db)
      TARGET_DB_KIND="${2:-}"
      shift 2
      ;;
    --backup-file)
      BACKUP_FILE="${2:-}"
      shift 2
      ;;
    --no-reset)
      RESET_DB=false
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

if [[ -z "$TARGET_DB_KIND" || -z "$BACKUP_FILE" ]]; then
  usage >&2
  exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

pick_docker_cmd

case "$TARGET_DB_KIND" in
  app)
    TARGET_DB_NAME="$(env_get "APP_DB_NAME")"
    TARGET_DB_USER="$(env_get "APP_DB_USER")"
    ;;
  directus)
    TARGET_DB_NAME="$(env_get "DIRECTUS_DB_NAME")"
    TARGET_DB_USER="$(env_get "DIRECTUS_DB_USER")"
    ;;
  *)
    echo "Unsupported --db value: $TARGET_DB_KIND" >&2
    exit 1
    ;;
esac

SUPERUSER="$(env_get "POSTGRES_SUPERUSER")"
SUPERPASSWORD="$(env_get "POSTGRES_SUPERPASSWORD")"

if [[ -z "$TARGET_DB_NAME" || -z "$TARGET_DB_USER" || -z "$SUPERUSER" || -z "$SUPERPASSWORD" ]]; then
  echo "Database credentials are incomplete in $ENV_FILE" >&2
  exit 1
fi

if [[ "$RESET_DB" == "true" ]]; then
  echo "Resetting public schema in $TARGET_DB_NAME"
  compose_infra exec -T database env PGPASSWORD="$SUPERPASSWORD" \
    psql -U "$SUPERUSER" -d "$TARGET_DB_NAME" -v ON_ERROR_STOP=1 \
    -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public AUTHORIZATION \"$TARGET_DB_USER\"; GRANT ALL ON SCHEMA public TO \"$TARGET_DB_USER\"; GRANT ALL ON SCHEMA public TO public;"
fi

echo "Importing $BACKUP_FILE into $TARGET_DB_NAME"
if [[ "$BACKUP_FILE" == *.gz ]]; then
  gzip -dc "$BACKUP_FILE" | compose_infra exec -T database env PGPASSWORD="$SUPERPASSWORD" \
    psql -U "$SUPERUSER" -d "$TARGET_DB_NAME" -v ON_ERROR_STOP=1
else
  cat "$BACKUP_FILE" | compose_infra exec -T database env PGPASSWORD="$SUPERPASSWORD" \
    psql -U "$SUPERUSER" -d "$TARGET_DB_NAME" -v ON_ERROR_STOP=1
fi

echo "PostgreSQL restore completed for $TARGET_DB_NAME"
