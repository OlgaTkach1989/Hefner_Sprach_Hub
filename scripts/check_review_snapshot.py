from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    ".editorconfig",
    ".gitattributes",
    ".github/CODEOWNERS",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/workflows/ci.yml",
    ".gitignore",
    "AUTHORS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE.md",
    "NOTICE.md",
    "README.md",
    "docs/PROFESSIONALIZATION_PLAN.md",
    "docs/REVIEWER_HANDOFF.md",
    "docs/REVIEW_SNAPSHOT_PLAN.md",
    "package.json",
    "scripts/check_review_snapshot.py",
    "scripts/run_backend_manage.py",
)

REQUIRED_PACKAGE_LOCKS = (
    "admin-console/package-lock.json",
    "learning-portal/package-lock.json",
    "learner-portal/package-lock.json",
    "instructor-workspace/package-lock.json",
)

FORBIDDEN_WORKTREE_FILES = (
    "learning-portal/pnpm-lock.yaml",
    "learning-portal/vite.config.d.ts",
    "learning-portal/vite.config.js",
    "learner-portal/pnpm-lock.yaml",
    "learner-portal/vite.config.d.ts",
    "learner-portal/vite.config.js",
)

ALLOWED_REVIEW_SNAPSHOT_PATHS = {
    ".editorconfig",
    ".env.example",
    ".gitattributes",
    ".github/CODEOWNERS",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/workflows/ci.yml",
    ".gitignore",
    "AUTHORS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE.md",
    "NOTICE.md",
    "README.md",
    "backend/.env.example",
    "backend/Studentlist/settings.py",
    "deploy/directus/README.md",
    "deploy/directus/training-content-sync.upsert.example.json",
    "docs/AI_ASSISTANT_DEMO.md",
    "docs/DEPLOYMENT.md",
    "docs/DEPLOYMENT_SPLIT_STACK.md",
    "docs/DIRECTUS_TRAINING_SETUP.md",
    "docs/GITHUB_AND_SERVER_CHECKLIST.md",
    "docs/OPERATIONS_RUNBOOK.md",
    "docs/PROFESSIONALIZATION_PLAN.md",
    "docs/REVIEWER_HANDOFF.md",
    "docs/REVIEW_SNAPSHOT_PLAN.md",
    "admin-console/package.json",
    "learning-portal/package.json",
    "learning-portal/pnpm-lock.yaml",
    "learning-portal/vite.config.d.ts",
    "learning-portal/vite.config.js",
    "learner-portal/package.json",
    "learner-portal/pnpm-lock.yaml",
    "learner-portal/vite.config.d.ts",
    "learner-portal/vite.config.js",
    "instructor-workspace/package.json",
    "package.json",
    "scripts/check_review_snapshot.py",
    "scripts/run_backend_manage.py",
}

TEXT_SCAN_PATHS = (
    "AUTHORS.md",
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE.md",
    "NOTICE.md",
    ".github",
    "docs",
)

LOCAL_PATH_PATTERN = re.compile(
    r"(?i)(?:[a-z]:[\\/](?:users|documents|onedrive)[\\/]|/c:/users[\\/]|file://)"
)


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def rel(path: Path) -> str:
    return path.relative_to(ROOT_DIR).as_posix()


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for item in TEXT_SCAN_PATHS:
        path = ROOT_DIR / item
        if path.is_file():
            files.append(path)
            continue
        if path.is_dir():
            files.extend(
                child
                for child in path.rglob("*")
                if child.is_file() and child.suffix.lower() in {".md", ".txt", ".yml", ".yaml"}
            )
    return sorted(files)


def check_required_files(errors: list[str]) -> None:
    for item in REQUIRED_FILES:
        if not (ROOT_DIR / item).is_file():
            errors.append(f"missing required review file: {item}")


def check_package_manager(errors: list[str]) -> None:
    for item in REQUIRED_PACKAGE_LOCKS:
        if not (ROOT_DIR / item).is_file():
            errors.append(f"missing npm lock file: {item}")

    for item in FORBIDDEN_WORKTREE_FILES:
        if (ROOT_DIR / item).exists():
            errors.append(f"generated or secondary package-manager file still exists: {item}")


def check_tracked_archives(errors: list[str]) -> None:
    result = run_git(["ls-files", "*.bundle", "*.tar", "*.tar.gz", "*.zip"])
    if result.returncode != 0:
        errors.append(f"git ls-files failed: {result.stderr.strip()}")
        return
    tracked = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if tracked:
        errors.append("archive/bundle files are tracked: " + ", ".join(tracked))


def check_local_paths(errors: list[str]) -> None:
    for path in iter_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for index, line in enumerate(text.splitlines(), start=1):
            if LOCAL_PATH_PATTERN.search(line):
                errors.append(f"machine-local path found in {rel(path)}:{index}")


def check_staged_scope(errors: list[str]) -> None:
    result = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMRTD"])
    if result.returncode != 0:
        errors.append(f"git diff --cached failed: {result.stderr.strip()}")
        return

    staged = [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]
    unexpected = [path for path in staged if path not in ALLOWED_REVIEW_SNAPSHOT_PATHS]
    if unexpected:
        errors.append("unexpected files staged for review snapshot: " + ", ".join(unexpected))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate repository review snapshot hygiene.")
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Also verify that staged files belong to the professionalization snapshot.",
    )
    args = parser.parse_args()

    errors: list[str] = []
    check_required_files(errors)
    check_package_manager(errors)
    check_tracked_archives(errors)
    check_local_paths(errors)
    if args.staged:
        check_staged_scope(errors)

    if errors:
        print("Review snapshot check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    scope_note = " including staged-file scope" if args.staged else ""
    print(f"Review snapshot check passed{scope_note}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
