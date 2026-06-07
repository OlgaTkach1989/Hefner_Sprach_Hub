#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "/usr/local/bin/learning-hub-singleuser-start.sh" ]; then
  shift
fi

if [ "${1:-}" = "jupyterhub-singleuser" ] || [ "${1:-}" = "/opt/conda/bin/jupyterhub-singleuser" ]; then
  shift
fi

NOTEBOOK_DIR="${JUPYTERHUB_NOTEBOOK_DIR:-/home/jovyan/work}"
CONTENT_ROOT="${TRAINING_CONTENT_ROOT:-/opt/training-content}"
CONTENT_ROOTS="${TRAINING_CONTENT_ROOTS:-}"
NOTEBOOK_PATH="${TRAINING_NOTEBOOK_PATH:-}"
NOTEBOOK_FORCE_RESET="${TRAINING_NOTEBOOK_FORCE_RESET:-0}"

mkdir -p "${NOTEBOOK_DIR}"

python - "${CONTENT_ROOT}" "${CONTENT_ROOTS}" "${NOTEBOOK_DIR}" "${NOTEBOOK_PATH}" <<'PY'
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

fallback_root = Path(sys.argv[1]).resolve()
configured_roots = str(sys.argv[2] or "").strip()
notebook_dir = Path(sys.argv[3]).resolve()
relative_path = str(sys.argv[4] or "").strip().lstrip("/")
if not relative_path:
    raise SystemExit(0)

target_path = (notebook_dir / relative_path).resolve()
content_roots = []
if configured_roots:
    for item in configured_roots.split(","):
        normalized = item.strip()
        if normalized:
            content_roots.append(Path(normalized).resolve())
content_roots.append(fallback_root)

def copy_missing_tree(source_root: Path, target_root: Path) -> None:
    if not source_root.exists() or not source_root.is_dir():
        return
    try:
        source_root.relative_to(source_root)
        target_root.relative_to(notebook_dir)
    except ValueError:
        return
    for source_path in sorted(source_root.rglob("*")):
        relative = source_path.relative_to(source_root)
        target_candidate = (target_root / relative).resolve()
        try:
            target_candidate.relative_to(notebook_dir)
        except ValueError:
            continue
        if source_path.is_dir():
            target_candidate.mkdir(parents=True, exist_ok=True)
            continue
        if target_candidate.exists():
            continue
        target_candidate.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_candidate)

for content_root in content_roots:
    labs_source = (content_root / "labs").resolve()
    labs_target = (notebook_dir / "labs").resolve()
    try:
        labs_source.relative_to(content_root)
        labs_target.relative_to(notebook_dir)
    except ValueError:
        continue
    copy_missing_tree(labs_source, labs_target)

source_path = None
for content_root in content_roots:
    candidate = (content_root / relative_path).resolve()
    try:
        candidate.relative_to(content_root)
        target_path.relative_to(notebook_dir)
    except ValueError:
        continue
    if candidate.exists():
        source_path = candidate
        break

force_reset = str(os.getenv("TRAINING_NOTEBOOK_FORCE_RESET") or "").strip().lower() in {"1", "true", "yes", "on"}

if source_path is None:
    raise SystemExit(0)

target_path.parent.mkdir(parents=True, exist_ok=True)
if force_reset and target_path.exists():
    if target_path.is_dir():
        shutil.rmtree(target_path)
    else:
        target_path.unlink()
elif target_path.exists():
    raise SystemExit(0)

if source_path.is_dir():
    shutil.copytree(source_path, target_path, dirs_exist_ok=True)
else:
    shutil.copy2(source_path, target_path)
PY

cd "${NOTEBOOK_DIR}"
exec jupyterhub-singleuser "$@"
