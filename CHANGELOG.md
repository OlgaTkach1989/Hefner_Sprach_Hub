# Changelog

All notable project-level changes should be documented here.

## Unreleased

### Added

- Root monorepo scripts for backend checks, frontend builds, Docker Compose validation, and full local verification.
- GitHub Actions CI for backend tests, frontend typecheck/build, and Docker Compose config rendering.
- Reviewer quickstart and professionalization plan for external technical review.
- Contributor guide and pull request template.
- Repository line-ending and binary-file attributes.

### Changed

- Frontend package scripts now run `tsc -b` before production builds.
- Vite commands explicitly use `vite.config.ts`.
- Environment examples use neutral placeholders and include env-driven `SECURE_SSL_REDIRECT`.
- Documentation links no longer use machine-local absolute paths.

### Removed

- Secondary `pnpm-lock.yaml` files from apps standardized on npm.
- Generated Vite `.js` and `.d.ts` config artifacts where `vite.config.ts` is the source of truth.

### Known Issues

- Live server HTTP checks pass, but port `443` is not currently listening.
- Vite emits non-failing chunk-size warnings for the frontend apps.
- Several large backend and frontend modules still need focused refactor passes.
