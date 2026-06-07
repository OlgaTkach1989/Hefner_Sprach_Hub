# Extraction Notes

This project was created next to `studentlist` as an isolated copy of the Learning Hub domain.

Safety guarantees:
- no files were edited inside `studentlist`
- all copied code lives under `Learning Hub`

Current architecture:
- backend keeps original app labels `users`, `employees`, `online` so that the extracted `apps.online` code remains close to source
- public and student frontends were copied as standalone apps
- teacher and admin frontends were extracted into standalone apps
- API is exposed under both:
  - `/api/online/`
  - `/online/`

Why both paths exist:
- `/api/online/` matches the frontend env examples
- `/online/` keeps compatibility with old code paths and copied tests

Current first-cut scope:
- public online catalog and checkout flow
- student auth and student cabinet
- teacher workspace with cohorts, calendar, open/end session, and attendance sync
- admin workspace with course/cohort dashboards and session lifecycle controls
- online data model, reminders, payment mock/free flow, attendance sync, Graph integration hooks
- online management through Django admin
- dockerized stack with pgvector, redis, directus, backend, nginx, and all extracted frontends
