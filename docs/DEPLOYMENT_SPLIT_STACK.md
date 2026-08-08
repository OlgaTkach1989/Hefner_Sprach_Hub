# Split Stack Deployment

This is the recommended production layout for `Hefner Sprach Hub`.

It is the layout I chose as the main server strategy because it matches the original architecture most closely:
- upper infra stack for `nginx + certbot + pgvector + redis + directus + backups`
- separate app stack for `backend + scheduler + public/student/teacher/admin`
- both stacks joined through one shared Docker network

## Layout

Top infra stack:
- nginx
- certbot
- PostgreSQL with pgvector
- Redis
- Directus
- DB backups

App stack:
- Django backend
- scheduler
- `learning-portal`
- `learner-portal`
- `instructor-workspace`
- `admin-console`

Both stacks communicate through the shared external Docker network `onlinelessons_shared`.

## Fast path on a fresh Ubuntu 24.04 server

After cloning the repository:

```bash
bash deploy/server/bootstrap-ubuntu.sh
bash deploy/server/deploy.sh --domain your-domain.example --email admin@your-domain.example
```

Operational references:
- [OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md)
- [DIRECTUS_TRAINING_SETUP.md](docs/DIRECTUS_TRAINING_SETUP.md)

The deploy script will:
- create `.env` from `.env.example` if needed
- fill domain-derived settings
- generate missing secrets automatically
- start the HTTP infra stack
- issue the first Let's Encrypt certificate
- switch infra to TLS mode
- build and start the app stack
- run HTTP smoke checks

## 1. Prepare root env

```powershell
cd <repo-root>
copy .env.example .env
```

Fill at minimum:
- `DJANGO_SECRET_KEY`
- `POSTGRES_SUPERPASSWORD`
- `APP_DB_PASSWORD`
- `DIRECTUS_DB_PASSWORD`
- `DIRECTUS_KEY`
- `DIRECTUS_SECRET`
- `DIRECTUS_ADMIN_PASSWORD`
- `CERTBOT_EMAIL`

Point DNS first:
- `A` record: `your-domain.example -> your-server-ip`
- optional `AAAA` record: `your-domain.example -> your-server-ipv6`

## 2. Start infra stack in HTTP mode

```powershell
docker compose -f deploy/infra/docker-compose.yml --env-file .env up -d
```

This brings up:
- `nginx`
- `postgres` on `pgvector/pgvector:pg16`
- `redis`
- `directus`
- backup services

`nginx` is configured to start even before the app stack exists, so certificate bootstrapping does not depend on backend/frontend containers already running.

## 3. Issue the first Let's Encrypt certificate

```powershell
bash deploy/infra/certbot/issue-initial-cert.sh
```

If you prefer the raw command instead of the helper script:

```powershell
docker compose -f deploy/infra/docker-compose.yml --env-file .env run --rm certbot certonly --webroot -w /var/www/certbot -d your-domain.example --email your-email@example.com --agree-tos --no-eff-email
```

## 4. Restart infra stack with TLS enabled

```powershell
docker compose -f deploy/infra/docker-compose.yml -f deploy/infra/docker-compose.tls.yml --env-file .env up -d
```

## 5. Start app stack

```powershell
docker compose -f deploy/app/docker-compose.yml --env-file .env up --build -d
```

## 6. URLs

- Public site: `${APP_BASE_URL}`
- Student cabinet: `${APP_BASE_URL}/student/`
- Teacher cabinet: `${APP_BASE_URL}/teacher/`
- Admin cabinet: `${APP_BASE_URL}/office/`
- Django admin: `${APP_BASE_URL}/admin/`
- API: `${APP_BASE_URL}/api/online/`
- Directus: `${APP_BASE_URL}/directus/`

Directus recovery access is loopback-only by default through `DIRECTUS_HTTP_BIND=127.0.0.1`.
Use an SSH tunnel when you need direct host access.

## 6a. Post-deploy smoke check

```bash
bash deploy/server/smoke-test.sh --domain your-domain.example
```

## 7. Why this is the recommended layout

- It mirrors the original server more closely than the single-stack compose.
- It keeps reverse proxy, DB, cache, Directus, and backups at the upper layer.
- It lets you add more apps later without rebuilding the whole server topology.
- It is better aligned with future AI-assistant expansion around `pgvector`.
