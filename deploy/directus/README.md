# Directus Operational Wiring

This folder documents the Directus-side contracts that `Hefner Sprach Hub` expects in production.

Required Directus flows:
- `online-email`
- `course-access`
- `training-content-sync`

Provisioning scripts:
- [setup_directus_communications.py](deploy/directus/setup_directus_communications.py)
- [setup_training_directus.py](deploy/directus/setup_training_directus.py)

Backend contracts:
- email flow URL -> `ONLINE_EMAIL_DIRECTUS_FLOW_URL`
- course access flow URL -> `ONLINE_COURSE_ACCESS_DIRECTUS_FLOW_URL`
- training content sync endpoint -> `POST /api/training/internal/directus/content-sync/`

Demo email delivery:
- Directus is wired to `Mailpit` by default in the deploy stack
- Mailpit UI is loopback-only on `127.0.0.1:${MAILPIT_HTTP_PORT:-8025}`
- inspect it over SSH tunnel when validating outbound emails

Security:
- `training-content-sync` must send `Authorization: Bearer ${TRAINING_DIRECTUS_SYNC_TOKEN}`
- do not expose the internal sync token in browser code or public collections

Examples:
- [training-content-sync.upsert.example.json](deploy/directus/training-content-sync.upsert.example.json)
- [training-content-sync.delete.example.json](deploy/directus/training-content-sync.delete.example.json)

Detailed operational procedure:
- [DIRECTUS_TRAINING_SETUP.md](docs/DIRECTUS_TRAINING_SETUP.md)
