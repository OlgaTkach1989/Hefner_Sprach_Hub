# Deployment

This is the fallback all-in-one Docker Compose stack. Use it when you want the fastest possible deployment on one host.

For the recommended production layout that mirrors the original server more closely, use [DEPLOYMENT_SPLIT_STACK.md](docs/DEPLOYMENT_SPLIT_STACK.md).

The all-in-one stack includes:
- PostgreSQL with pgvector
- Redis
- Directus
- Django backend
- `learning-portal`
- `learner-portal`
- `instructor-workspace`
- `admin-console`
- Nginx reverse proxy

## 1. Prepare environment

```powershell
cd <repo-root>
copy .env.example .env
```

Review at minimum:
- `APP_BASE_URL`
- `NGINX_SERVER_NAME`
- `DJANGO_SECRET_KEY`
- `POSTGRES_SUPERPASSWORD`
- `APP_DB_PASSWORD`
- `DIRECTUS_DB_PASSWORD`
- `DIRECTUS_KEY`
- `DIRECTUS_SECRET`
- `DIRECTUS_ADMIN_EMAIL`
- `DIRECTUS_ADMIN_PASSWORD`

## 2. Build and start

```powershell
docker compose up --build -d
```

## 3. URLs

- Main public site: `${APP_BASE_URL}`
- Student cabinet: `${APP_BASE_URL}/student/`
- Teacher cabinet: `${APP_BASE_URL}/teacher/`
- Admin cabinet: `${APP_BASE_URL}/office/`
- Django admin: `${APP_BASE_URL}/admin/`
- API: `${APP_BASE_URL}/api/online/`
- Directus: `${APP_BASE_URL}/directus/`

Directus host publishing is loopback-only by default through `DIRECTUS_HTTP_BIND=127.0.0.1`.

## 4. Demo data inside Docker

Create demo admin:

```powershell
docker compose exec backend python manage.py shell -c "from apps.users.models import User; user, _ = User.objects.get_or_create(email='admin@learning-hub.local', defaults={'username': 'online_admin_local'}); user.is_admin = True; user.is_staff = True; user.is_superuser = True; user.set_password('AdminPass12345!'); user.save(); print(user.email)"
```

Create demo teacher and cohort:

```powershell
docker compose exec backend python manage.py setup_online_demo_flow --teacher-email teacher@learning-hub.local --teacher-password TeacherPass12345! --course-slug paint-in-5-days --cohort-code ONLINE_TEACHER_G1 --students 3 --starts-in-minutes 30 --duration-minutes 90 --reschedule-existing
```

## 5. Notes about Directus

- The stack mirrors the original server idea: `pgvector + redis + directus` next to the app.
- Backend integration points are already exposed through:
  - `ONLINE_EMAIL_DIRECTUS_FLOW_URL`
  - `ONLINE_COURSE_ACCESS_DIRECTUS_FLOW_URL`
  - `ONLINE_EMAIL_DIRECTUS_TOKEN`
- For first boot you can keep `ONLINE_EMAIL_MODE=console` and switch to `directus_flow` later when your flows are ready.
- For training content publishing, wire the protected endpoint described in [DIRECTUS_TRAINING_SETUP.md](docs/DIRECTUS_TRAINING_SETUP.md).
