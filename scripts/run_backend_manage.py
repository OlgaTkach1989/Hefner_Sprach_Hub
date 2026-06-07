from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
MANAGE_PY = BACKEND_DIR / "manage.py"


def resolve_python() -> str:
    windows_venv_python = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    posix_venv_python = BACKEND_DIR / ".venv" / "bin" / "python"

    if windows_venv_python.exists():
        return str(windows_venv_python)
    if posix_venv_python.exists():
        return str(posix_venv_python)
    return sys.executable


def main() -> int:
    if not MANAGE_PY.exists():
        print(f"Cannot find Django manage.py at {MANAGE_PY}", file=sys.stderr)
        return 2

    command = [resolve_python(), str(MANAGE_PY), *sys.argv[1:]]
    return subprocess.call(command, cwd=str(BACKEND_DIR), env=os.environ.copy())


if __name__ == "__main__":
    raise SystemExit(main())
