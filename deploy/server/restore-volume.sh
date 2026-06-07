#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/server/common.sh
source "$SCRIPT_DIR/common.sh"

ARCHIVE_PATH=""
VOLUME_NAME=""
FORCE=false

usage() {
  cat <<'EOF'
Usage:
  bash deploy/server/restore-volume.sh --archive /path/to/archive.tar.gz --volume onlinelessons_media --force

Options:
  --archive <path>          Tar.gz archive created by backup-volumes.sh
  --volume <name>           Docker volume to restore into
  --force                   Required. Existing volume contents will be deleted.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --archive)
      ARCHIVE_PATH="${2:-}"
      shift 2
      ;;
    --volume)
      VOLUME_NAME="${2:-}"
      shift 2
      ;;
    --force)
      FORCE=true
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

if [[ -z "$ARCHIVE_PATH" || -z "$VOLUME_NAME" ]]; then
  usage >&2
  exit 1
fi

if [[ "$FORCE" != "true" ]]; then
  echo "--force is required because restore is destructive for the target volume." >&2
  exit 1
fi

if [[ ! -f "$ARCHIVE_PATH" ]]; then
  echo "Archive not found: $ARCHIVE_PATH" >&2
  exit 1
fi

pick_docker_cmd

archive_dir="$(cd "$(dirname "$ARCHIVE_PATH")" && pwd)"
archive_file="$(basename "$ARCHIVE_PATH")"

echo "Restoring $archive_file into volume $VOLUME_NAME"
"${DOCKER_CMD[@]}" run --rm \
  -v "${VOLUME_NAME}:/target" \
  -v "${archive_dir}:/archive:ro" \
  alpine:3.21 \
  sh -c "rm -rf /target/* /target/.[!.]* /target/..?* 2>/dev/null || true; tar xzf /archive/${archive_file} -C /target"

echo "Restore completed for volume $VOLUME_NAME"
