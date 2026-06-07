from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings


NOTEBOOK_RUNTIME_ROOT_PREFIX = "training/runtime-content"


@dataclass(frozen=True)
class StoredRuntimeNotebook:
    notebook_path: str
    storage_path: str
    checksum: str
    size_bytes: int


def runtime_content_root() -> Path:
    return (Path(settings.MEDIA_ROOT) / NOTEBOOK_RUNTIME_ROOT_PREFIX).resolve()


def resolve_runtime_notebook_absolute_path(notebook_path: str) -> Path:
    normalized = str(notebook_path or "").strip().lstrip("/")
    if not normalized:
        raise ValueError("Notebook path is required.")
    root = runtime_content_root()
    absolute_path = (root / normalized).resolve()
    absolute_path.relative_to(root)
    return absolute_path


def store_runtime_notebook_bytes(*, content_slug: str, filename: str, notebook_bytes: bytes) -> StoredRuntimeNotebook:
    safe_slug = _safe_segment(content_slug or "notebook")
    safe_filename = _safe_filename(filename or f"{safe_slug}.ipynb")
    notebook_path = f"labs/{safe_slug}/{safe_filename}"
    absolute_path = resolve_runtime_notebook_absolute_path(notebook_path)
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(notebook_bytes)
    return StoredRuntimeNotebook(
        notebook_path=notebook_path,
        storage_path=str(absolute_path.relative_to(Path(settings.MEDIA_ROOT).resolve()).as_posix()),
        checksum=hashlib.sha256(notebook_bytes).hexdigest(),
        size_bytes=len(notebook_bytes),
    )


def store_runtime_notebook_text(*, content_slug: str, filename: str, text: str) -> StoredRuntimeNotebook:
    return store_runtime_notebook_bytes(
        content_slug=content_slug,
        filename=filename,
        notebook_bytes=text.encode("utf-8"),
    )


def _safe_segment(value: str) -> str:
    candidate = "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in value)
    return candidate.strip("-_") or "notebook"


def _safe_filename(value: str) -> str:
    candidate = Path(value).name
    if not candidate.endswith(".ipynb"):
        stem = Path(candidate).stem or "notebook"
        candidate = f"{stem}.ipynb"
    return candidate
