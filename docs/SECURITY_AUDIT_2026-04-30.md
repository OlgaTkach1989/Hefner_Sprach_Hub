# Security Audit Record - 2026-04-30

## Scope

- Backend/Django/API authentication, authorization, cookies, CORS, CSRF, health checks, webhooks, file delivery.
- Frontend dependency advisories for `learning-portal`, `learner-portal`, `instructor-workspace`, and `admin-console`.
- Python dependency advisories for `backend/requirements.txt`.
- Docker Compose, nginx TLS, certificate issuance scripts, and CI hardening gates.

## Closed Findings

- Upgraded unsupported `Django==5.1.15` to `Django==5.2.13` LTS.
- Upgraded vulnerable `requests==2.32.4` to `requests==2.33.0`.
- Upgraded vulnerable frontend packages and lock files:
  - `vite` to `^6.4.2`
  - `axios` to `^1.15.2`
  - transitive `follow-redirects` and `postcss`
  - `dompurify` override for `learner-portal` because of the Monaco dependency chain.
- Changed DRF default permissions from `AllowAny` to `IsAuthenticated`; public endpoints now opt in explicitly.
- Hardened online login and staff login errors to avoid user enumeration and added throttling to auth/magic-link endpoints.
- Made production `SECRET_KEY`/`DJANGO_SECRET_KEY` and `ALLOWED_HOSTS` mandatory.
- Blocked unsafe production CORS configuration with credentials and wildcard origins.
- Required constant-time payment webhook signature validation when signature enforcement is enabled.
- Redacted operational health-check details unless `HEALTHCHECK_EXPOSE_DETAILS=true`.
- Added CSP sandbox and `nosniff` to HTML grading artifacts.
- Removed direct public nginx serving of `/media/`; course files and avatars now go through authenticated API endpoints.
- Hardened nginx TLS and headers: TLS 1.2/1.3, session tickets disabled, HSTS, `nosniff`, frame, referrer, and permissions policies.
- Removed weak database password fallbacks from Compose files.
- Added `no-new-privileges:true` to Compose services.
- Reworked initial cert issuance script so it no longer sources `.env` as shell code.
- Added CI checks for weak secret fallbacks and nginx TLS hardening.

## Verification

- `python -m pip_audit -r backend/requirements.txt`
- `npm --prefix learning-portal audit --audit-level=moderate`
- `npm --prefix learner-portal audit --audit-level=moderate`
- `npm --prefix instructor-workspace audit --audit-level=moderate`
- `npm --prefix admin-console audit --audit-level=moderate`
- `python scripts/run_backend_manage.py check`
- `python scripts/run_backend_manage.py check --deploy` with explicit production env.
- `npm run verify:local`
- `git diff --check`
- Docker Compose render checks through `npm run compose:config:all`.

## Remaining Non-Blocking Notes

- Vite still reports chunk-size warnings after production builds. This is performance work, not an active security vulnerability.
- HSTS preload headers are enabled for production. Submitting the domain to browser preload lists remains an operational decision.
