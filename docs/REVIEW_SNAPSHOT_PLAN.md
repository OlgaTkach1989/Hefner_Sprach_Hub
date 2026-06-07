# Review Snapshot Plan

This file lists the intended professionalization snapshot so it can be staged without pulling in unrelated runtime work from the current dirty workspace.

## Goal

Create a reviewable commit or tag that contains repository maturity improvements only:

- validation entrypoints
- CI
- contributor/reviewer documentation
- environment examples
- package-manager cleanup
- generated config cleanup

Do not use this snapshot to include unrelated feature work, UI edits, backend domain changes, or deployment runtime changes.

## Candidate Commit 1: Tooling and CI

Files:

```text
.editorconfig
.gitattributes
.gitignore
.github/workflows/ci.yml
.github/PULL_REQUEST_TEMPLATE.md
package.json
scripts/run_backend_manage.py
admin-console/package.json
learning-portal/package.json
learner-portal/package.json
instructor-workspace/package.json
learning-portal/pnpm-lock.yaml
learning-portal/vite.config.d.ts
learning-portal/vite.config.js
learner-portal/pnpm-lock.yaml
learner-portal/vite.config.d.ts
learner-portal/vite.config.js
```

Suggested staging command:

```powershell
git add -- .editorconfig .gitattributes .gitignore .github/workflows/ci.yml .github/PULL_REQUEST_TEMPLATE.md package.json scripts/run_backend_manage.py admin-console/package.json learning-portal/package.json learner-portal/package.json instructor-workspace/package.json
git add -u -- learning-portal/pnpm-lock.yaml learning-portal/vite.config.d.ts learning-portal/vite.config.js learner-portal/pnpm-lock.yaml learner-portal/vite.config.d.ts learner-portal/vite.config.js
```

Suggested commit message:

```text
chore: add monorepo validation and ci baseline
```

## Candidate Commit 2: Review Handoff and Examples

Files:

```text
README.md
CHANGELOG.md
CONTRIBUTING.md
.env.example
backend/.env.example
backend/Studentlist/settings.py
deploy/directus/README.md
deploy/directus/training-content-sync.upsert.example.json
docs/AI_ASSISTANT_DEMO.md
docs/DEPLOYMENT.md
docs/DEPLOYMENT_SPLIT_STACK.md
docs/DIRECTUS_TRAINING_SETUP.md
docs/GITHUB_AND_SERVER_CHECKLIST.md
docs/OPERATIONS_RUNBOOK.md
docs/PROFESSIONALIZATION_PLAN.md
docs/REVIEWER_HANDOFF.md
docs/REVIEW_SNAPSHOT_PLAN.md
```

Suggested staging command:

```powershell
git add -- README.md CHANGELOG.md CONTRIBUTING.md .env.example backend/.env.example backend/Studentlist/settings.py deploy/directus/README.md deploy/directus/training-content-sync.upsert.example.json docs/AI_ASSISTANT_DEMO.md docs/DEPLOYMENT.md docs/DEPLOYMENT_SPLIT_STACK.md docs/DIRECTUS_TRAINING_SETUP.md docs/GITHUB_AND_SERVER_CHECKLIST.md docs/OPERATIONS_RUNBOOK.md docs/PROFESSIONALIZATION_PLAN.md docs/REVIEWER_HANDOFF.md docs/REVIEW_SNAPSHOT_PLAN.md
```

Suggested commit message:

```text
docs: add reviewer handoff and professionalization plan
```

## Keep Out of This Snapshot

The current workspace contains additional modified or untracked runtime files. Review them separately before staging.

Do not include these groups in the professionalization snapshot unless they are intentionally reviewed as separate feature work:

- `backend/apps/online/**`
- `backend/apps/training/**`
- `backend/Dockerfile`
- `deploy/app/docker-compose.yml`
- `admin-console/src/**`
- `learning-portal/src/**`
- `learner-portal/src/**`
- `instructor-workspace/src/**`
- untracked product, sales, security, and compliance documents not listed above
- local archive and bundle files

## Required Checks Before Tagging

Run:

```powershell
git diff --check
npm run review:check
npm run review:check:staged
npm run verify:local
```

For the current server, use read-only checks unless a deploy is explicitly approved:

```powershell
ssh <server> "cd /opt/learning-hub && docker compose --env-file .env -f deploy/app/docker-compose.yml exec -T backend python manage.py check"
ssh <server> "cd /opt/learning-hub && docker compose --env-file .env -f deploy/app/docker-compose.yml exec -T backend python manage.py migrate --check"
```
