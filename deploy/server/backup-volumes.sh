#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/server/common.sh
source "$SCRIPT_DIR/common.sh"

OUTPUT_DIR=""
declare -a VOLUMES=()

usage() {
  cat <<'EOF'
Usage:
  bash deploy/server/backup-volumes.sh [options]

Options:
  --env-file <path>         Override env file
  --output-dir <path>       Target directory for tar.gz archives
  --volume <name>           Add a specific Docker volume to back up
  --all                     Back up all default mutable volumes

Default volumes:
  onlinelessons_media
  onlinelessons_directus_uploads
  jupyterhub_data
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --volume)
      VOLUMES+=("${2:-}")
      shift 2
      ;;
    --all)
      VOLUMES=("onlinelessons_media" "onlinelessons_directus_uploads" "jupyterhub_data")
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

pick_docker_cmd

if [[ ${#VOLUMES[@]} -eq 0 ]]; then
  VOLUMES=("onlinelessons_media" "onlinelessons_directus_uploads" "jupyterhub_data")
fi

if [[ -z "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR="$HOME/learning-hub-backups/volumes/$(date +%Y%m%d-%H%M%S)"
fi

mkdir -p "$OUTPUT_DIR"

for volume in "${VOLUMES[@]}"; do
  "${DOCKER_CMD[@]}" volume inspect "$volume" >/dev/null 2>&1
  archive_name="${volume}.tar.gz"
  echo "Backing up volume $volume -> $OUTPUT_DIR/$archive_name"
  "${DOCKER_CMD[@]}" run --rm \
    -v "${volume}:/source:ro" \
    -v "${OUTPUT_DIR}:/backup" \
    alpine:3.21 \
    sh -c "cd /source && tar czf /backup/${archive_name} ."
done

printf '%s\n' "${VOLUMES[@]}" > "$OUTPUT_DIR/manifest.volumes.txt"
echo "Volume backup complete: $OUTPUT_DIR"
