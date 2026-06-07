# Contributing

This repository is a Django + React monorepo. Keep changes small, reviewable, and covered by the checks that match the touched surface.

## Local Setup

Install backend dependencies into `backend/.venv` and install each frontend with npm:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm --prefix learning-portal ci
npm --prefix learner-portal ci
npm --prefix instructor-workspace ci
npm --prefix admin-console ci
```

## Required Checks

Run the full local gate before a review snapshot:

```powershell
npm run verify:local
```

For smaller changes, run the relevant subset:

```powershell
npm run backend:check
npm run backend:migrations:check
npm run backend:test
npm run typecheck
npm run build
npm run compose:config:all
```

## Change Discipline

- Keep tooling, documentation, and runtime behavior changes in separate commits.
- Do not commit `.env` files, database files, local archives, bundles, build output, or `node_modules`.
- Use npm as the frontend package manager for this baseline; do not add secondary lock files.
- Keep `vite.config.ts` as the Vite source of truth.
- Do not change production security defaults, permissions, Docker runtime users, or deployment flow in broad cleanup commits.
- Add or update tests when changing backend behavior, API contracts, permissions, schedulers, or training workflows.
- Treat server checks as read-only unless a deploy has been explicitly approved.

## Pull Request Expectations

Every pull request should include:

- What changed.
- Why it changed.
- User-visible or operational risk.
- Exact checks run.
- Whether a deployment is required.
