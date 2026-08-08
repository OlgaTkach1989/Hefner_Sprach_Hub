# Professionalization Plan

This plan is the execution order for preparing `Hefner Sprach Hub` for external technical review without changing application behavior.

## Guardrails

- Keep the currently working application behavior intact.
- Start with repository packaging, CI, documentation, and verification.
- Do not refactor large runtime modules in the same change set as tooling setup.
- Do not delete local backup artifacts automatically; ignore them and move them only after explicit owner confirmation.
- Run local checks before any server action.
- Treat server verification as read-only unless a deploy has been explicitly approved.

## Agent Assignments

### Repo and documentation agent

Scope:
- `.gitignore`
- `.editorconfig`
- `README.md`
- `docs/*`
- `.env.example`
- `backend/.env.example`

Tasks:
- Keep generated archives and temporary agent files out of version control.
- Replace machine-local documentation links with relative repository links.
- Replace personal or environment-specific values in examples with neutral placeholders.
- Maintain a reviewer quickstart and handoff checklist.
- Maintain contributor, changelog, and pull-request guidance.
- Maintain a review snapshot plan so repository cleanup can be staged separately from runtime changes.

### Frontend and tooling agent

Scope:
- root `package.json`
- `learning-portal/package.json`
- `learner-portal/package.json`
- `instructor-workspace/package.json`
- `admin-console/package.json`
- frontend build and type-check commands

Tasks:
- Provide one root entrypoint for all frontend builds.
- Keep existing app package files stable.
- Standardize the package manager recommendation before removing lock files.
- Defer route-level code splitting until the project is green with CI.

### Backend and deploy agent

Scope:
- `backend/`
- `docker-compose.yml`
- `deploy/app/docker-compose.yml`
- `deploy/infra/docker-compose.yml`
- `deploy/server/*`
- `.github/workflows/*`

Tasks:
- Keep backend checks and tests reproducible.
- Validate migrations are committed.
- Validate Docker Compose renders with example env.
- Record security hardening items separately from behavior-preserving changes.
- Defer Docker runtime changes such as non-root users or migration job extraction until after baseline CI is stable.

## Execution Order

### Phase 1: Low-risk repository packaging

Status: completed for the behavior-preserving baseline pass.

Tasks:
- Add ignore rules for local archives and temporary agent output.
- Add `.editorconfig`.
- Add or normalize `.gitattributes`.
- Add root monorepo convenience scripts.
- Add CI workflow for backend tests, frontend builds, and Docker Compose config validation.
- Add review snapshot hygiene checks.
- Clean environment examples and README links.
- Add reviewer handoff, contributor guide, changelog, and PR template.
- Add review snapshot plan for selective staging from the dirty workspace.
- Add explicit `typecheck` scripts for every frontend app.
- Force Vite commands to use `vite.config.ts` so generated `vite.config.js` files cannot shadow the TypeScript config.
- Standardize frontend dependency management on npm for the current baseline and remove secondary `pnpm-lock.yaml` files.
- Remove generated Vite `.js` / `.d.ts` config artifacts where `vite.config.ts` is the source of truth.

Verification:
- `git diff --check`
- `npm run backend:check`
- `npm run backend:migrations:check`
- `npm run build`
- `npm run compose:config:all`

Latest result:
- Passed on 2026-04-30 as part of `npm run verify:local`.

### Phase 2: Baseline regression verification

Status: completed locally for the behavior-preserving baseline pass.

Tasks:
- Run the full backend test suite.
- Capture frontend build warnings.
- Confirm no migration drift.
- Confirm CI commands match local commands.

Verification:
- `npm run backend:test`
- `npm run verify:local`

Latest result:
- `npm run verify:local` passed on 2026-04-30.
- `verify:local` includes the review snapshot hygiene check.
- Backend test command discovered and passed 352 tests.
- All four frontend apps passed `tsc -b` and production Vite builds.
- Docker Compose config validation passed for root, infra, infra+TLS, and app stacks.
- Vite still reports non-failing chunk-size warnings; route-level splitting is deferred.

Known deploy-check notes:
- `SECURE_SSL_REDIRECT` is env-driven and defaults to `false`; the split-stack HTTPS nginx template performs external HTTP-to-HTTPS redirects.
- `SECURE_HSTS_PRELOAD` is intentionally not enabled by default because preload affects the browser preload list and should be activated only after domain-level review.
- Placeholder `SECRET_KEY` values in example env files are expected to trigger deploy-check warnings until replaced in a real environment.

### Phase 3: Review handoff cleanup

Tasks:
- Move local backup archives outside the repository workspace after owner approval.
- Confirm no secondary package-manager lock files remain in committed sources.
- Keep `CHANGELOG.md` updated when a tagged review snapshot is created.
- Tag a reviewer snapshot.

Verification:
- `git status --short`
- `git ls-files | Select-String -Pattern "package-lock\\.json|pnpm-lock\\.yaml|\\.(tar|tar\\.gz|bundle|zip)$"`

### Phase 4: Architecture refactor planning

Tasks:
- Split `backend/apps/online/views.py` by API surface.
- Split `backend/apps/training/views.py` by API surface.
- Split large backend test modules by domain.
- Extract large React page sections into components and hooks.
- Split large CSS files into component-scoped modules.

Rules:
- One surface per pull request.
- No frontend and backend refactor in the same pull request unless an API contract changes.
- Each refactor must have before/after regression checks.

### Phase 5: Security hardening planning

Tasks:
- Change DRF default permissions from `AllowAny` to authenticated-by-default only after all public endpoints are explicitly marked and covered by tests.
- Split Django settings into base/local/production or equivalent environment profile.
- Add explicit production settings for HTTPS redirect and HSTS policy.
- Review Docker runtime users and migration execution strategy.

Rules:
- Do not combine permission default changes with unrelated cleanup.
- Add tests proving public endpoints remain public and private endpoints remain private.

### Phase 6: Server verification

Status: completed as read-only verification. The live server is healthy over HTTP; HTTPS smoke currently fails because the active nginx container publishes port 80 only.

Latest result:
- App stack containers are running; backend and JupyterHub report healthy container status.
- Infra stack containers are running; database, cache, Directus, Mailpit, and backup containers report healthy status where health checks are defined.
- `python manage.py check` passed inside the live backend container.
- `python manage.py migrate --check` passed inside the live backend container.
- `python manage.py check --deploy` completed with the expected TLS/HSTS advisory warnings: `security.W008` and `security.W021`.
- HTTP route smoke passed: `/`, `/student/`, `/teacher/`, `/office/`, and `/api/online/public/courses/` returned `200`; `/directus/` and `/lab/` returned `302`.
- `/api/health/ready/` and `/healthz` returned `ready: true` with no health warnings.
- Listening ports confirm `80` is active, `443` is not active, and Directus/Mailpit admin ports are bound to localhost only.

Read-only checks:
- `docker compose -f deploy/infra/docker-compose.yml --env-file .env ps`
- `docker compose -f deploy/app/docker-compose.yml --env-file .env ps`
- `bash deploy/server/smoke-test.sh`
- `curl -fsS http://<domain>/api/health/`
- `curl -fsS http://<domain>/api/health/ready/`
- `curl -fsS http://<domain>/healthz`

Post-deploy checks, only after deploy approval:
- Capture current container state.
- Confirm recent backups exist.
- Deploy with the existing deploy script.
- Repeat smoke tests.
- Tail backend, nginx, directus, and jupyterhub logs.

## Current Deferred Items

- Removing archive files from the workspace.
- Redacting or splitting environment-specific VPS handoff notes from generic product documentation.
- Refactoring large backend and frontend modules.
- Changing DRF default permissions.
- Changing Docker runtime behavior.
- Enforcing lint as a failing CI gate.
