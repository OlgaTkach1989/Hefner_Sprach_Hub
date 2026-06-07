# Reviewer Handoff

This document gives an external reviewer a compact entrypoint into the current project state.

## Review Objective

Assess whether the repository is maintainable, reproducible, and ready for staged hardening without changing the currently working application behavior.

## Current Baseline

Last local verification: 2026-04-30.

Result:
- `npm run verify:local` passed.
- `verify:local` includes repository hygiene checks for the professionalization snapshot.
- Django system check passed.
- Migration drift check passed.
- Backend tests passed: 352 tests.
- All four frontend apps passed typecheck and production build.
- Docker Compose config rendering passed for root, infra, infra+TLS, and app stacks.

Server verification was read-only. No deploy was performed.

Server result:
- App and infra containers were running.
- Backend and JupyterHub containers reported healthy status.
- Live backend `manage.py check` passed.
- Live backend `manage.py migrate --check` passed.
- HTTP route smoke passed for the main public, student, teacher, admin, and public course endpoints.
- Health endpoints returned `ready: true`.
- HTTPS is not currently active because port `443` is not listening.
- `manage.py check --deploy` reports the expected TLS/HSTS advisory warnings until the HTTPS posture is finalized.

## Recommended Review Path

1. Read [README.md](../README.md) for setup and validation commands.
2. Read [PROFESSIONALIZATION_PLAN.md](PROFESSIONALIZATION_PLAN.md) for execution phases and deferred risk.
3. Read [REVIEW_SNAPSHOT_PLAN.md](REVIEW_SNAPSHOT_PLAN.md) before staging a review commit from a dirty workspace.
4. Review [ARCHITECTURE_AND_DATA_FLOW.md](ARCHITECTURE_AND_DATA_FLOW.md) for system shape.
5. Review [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md) and [DEPLOYMENT_SPLIT_STACK.md](DEPLOYMENT_SPLIT_STACK.md) for operations and deployment.
6. Review [SECURITY_REVIEW_CHECKLIST.md](SECURITY_REVIEW_CHECKLIST.md) and [CUSTOMER_SECURITY_PACK.md](CUSTOMER_SECURITY_PACK.md) for security/compliance readiness.

## Local Validation

Use the full gate for a clean checkout:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm --prefix learning-portal ci
npm --prefix learner-portal ci
npm --prefix instructor-workspace ci
npm --prefix admin-console ci
npm run verify:local
```

## Review Boundaries

- The project currently has existing runtime changes in the working tree. Review snapshots should be staged intentionally rather than committing every modified file together.
- The professionalization baseline is intentionally limited to tooling, docs, CI, examples, and validation entrypoints.
- Large runtime refactors, permission defaults, Docker runtime behavior, and TLS/HSTS production settings are deferred to dedicated changes.
- Archive and bundle files are ignored by Git and should be moved out of the repository workspace only after owner approval.

## Known Follow-Ups

- Bring HTTPS back into service and rerun the server smoke test over HTTPS.
- Split large backend view/test modules by API surface.
- Split large frontend pages into smaller components and route-level chunks.
- Add lint formatting policy after the baseline remains green.
- Create a tagged review snapshot after selecting the exact files that belong to the professionalization commit.
