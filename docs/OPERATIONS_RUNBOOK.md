# Operations Runbook

This runbook is the operational source of truth for `Learning Hub` on Ubuntu 24.04 servers.

## Stack

Infra stack:
- `nginx`
- `certbot`
- `database` (`pgvector/pgvector:pg16`)
- `cache`
- `mailpit`
- `directus`
- `db_backup_app`
- `db_backup_directus`

App stack:
- `backend`
- `scheduler`
- `traininggrader`
- `jupyterhub`
- `learning-portal`
- `learner-portal`
- `instructor-workspace`
- `admin-console`

## Daily commands

Infra status:
```bash
docker compose -f deploy/infra/docker-compose.yml --env-file .env ps
```

App status:
```bash
docker compose -f deploy/app/docker-compose.yml --env-file .env ps
```

Smoke test:
```bash
bash deploy/server/smoke-test.sh
```

Backend logs:
```bash
docker compose -f deploy/app/docker-compose.yml --env-file .env logs -f backend
```

Directus logs:
```bash
docker compose -f deploy/infra/docker-compose.yml --env-file .env logs -f directus
```

Mailpit logs:
```bash
docker compose -f deploy/infra/docker-compose.yml --env-file .env logs -f mailpit
```

JupyterHub logs:
```bash
docker compose -f deploy/app/docker-compose.yml --env-file .env logs -f jupyterhub
```

## Deploy/update

Standard deploy:
```bash
bash deploy/server/deploy.sh --domain your-domain.example --email admin@your-domain.example
```

Fast redeploy without rebuild:
```bash
bash deploy/server/deploy.sh --skip-build
```

The deploy script now:
- updates `.env`
- generates missing runtime secrets
- pins `DIRECTUS_HTTP_BIND=127.0.0.1` by default
- provisions Directus training and communication flows
- starts infra and app stacks
- runs post-deploy smoke verification

## Health endpoints

Liveness:
```text
/api/health/
```

Readiness:
```text
/api/health/ready/
/healthz
```

Readiness checks:
- database connectivity
- media/static directories
- cache write/read
- pgvector availability when enabled
- config completeness for Directus/Jupyter/grader features

## Backups

Database dumps are created automatically by:
- `db_backup_app`
- `db_backup_directus`

To inspect DB backup files:
```bash
docker run --rm -v onlinelessons_backups:/backups alpine:3.21 ls -lah /backups
```

To snapshot mutable Docker volumes:
```bash
bash deploy/server/backup-volumes.sh --all
```

Default volumes:
- `onlinelessons_media`
- `onlinelessons_directus_uploads`
- `jupyterhub_data`

## Restore order

Recommended full restore order:
1. Restore application DB
2. Restore Directus DB
3. Restore `onlinelessons_directus_uploads`
4. Restore `onlinelessons_media`
5. Restore `jupyterhub_data`
6. Restart stacks
7. Rebuild training knowledge index
8. Run smoke test

Restore app DB:
```bash
bash deploy/server/restore-postgres.sh --db app --backup-file /path/to/app.sql.gz
```

Restore Directus DB:
```bash
bash deploy/server/restore-postgres.sh --db directus --backup-file /path/to/directus.sql.gz
```

Restore a volume:
```bash
bash deploy/server/restore-volume.sh --archive /path/to/onlinelessons_media.tar.gz --volume onlinelessons_media --force
```

Rebuild the knowledge index after restore:
```bash
docker compose -f deploy/app/docker-compose.yml --env-file .env exec backend \
  python manage.py rebuild_training_knowledge_index
```

Post-restore smoke check:
```bash
bash deploy/server/smoke-test.sh
```

## Directus recovery/admin access

`DIRECTUS_HTTP_BIND` is loopback-only by default. This is intentional.

Recovery/admin tunnel:
```bash
ssh -L 8055:127.0.0.1:8055 ubuntu@your-server-ip
ssh -L 8025:127.0.0.1:8025 ubuntu@your-server-ip
```

Then open:
```text
http://127.0.0.1:8055
http://127.0.0.1:8025
```

If you need temporary non-loopback access, change `DIRECTUS_HTTP_BIND` in `.env`, redeploy, complete the task, then revert it.

## AI and training operations

Manual index rebuild:
```bash
docker compose -f deploy/app/docker-compose.yml --env-file .env exec backend \
  python manage.py rebuild_training_knowledge_index
```

Process grader jobs manually:
```bash
docker compose -f deploy/app/docker-compose.yml --env-file .env exec traininggrader \
  python manage.py process_training_grader_jobs --limit 20
```

Seed demo AI content:
```bash
docker compose -f deploy/app/docker-compose.yml --env-file .env exec backend \
  python manage.py seed_training_ai_demo --student-email admin@learning-hub.local
```

## Incident checklist

If the site is down:
1. `docker compose ... ps` for both stacks
2. `bash deploy/server/smoke-test.sh`
3. inspect `backend`, `directus`, `jupyterhub`, `nginx` logs
4. check `/api/health/ready/`
5. verify DB dumps still exist in `onlinelessons_backups`
6. if Directus content drift is suspected, re-run knowledge index rebuild

If Directus content stopped syncing:
1. verify `TRAINING_DIRECTUS_SYNC_TOKEN` in `.env`
2. verify the Directus flow/webhook in [DIRECTUS_TRAINING_SETUP.md](/docs/DIRECTUS_TRAINING_SETUP.md)
3. inspect `TrainingContentSyncEvent` in Django admin
4. inspect `TrainingAuditEvent` entries `directus.sync_failed`
5. re-run `python manage.py rebuild_training_knowledge_index` if content was recovered manually
