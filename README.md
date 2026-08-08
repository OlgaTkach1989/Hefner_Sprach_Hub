# Hefner Sprach Hub

Standalone Hefner Sprach Hub platform extracted from the original `studentlist` project.

What is included:
- `backend/`: Django backend with `users`, `employees`, and the stable `online` domain app
- `learning-portal/`: public catalog, checkout, magic-link portal
- `learner-portal/`: student login and cabinet
- `instructor-workspace/`: standalone teacher workspace
- `admin-console/`: standalone admin workspace
- scheduler workers for reminders, attendance sync, and session lifecycle automation

What is intentionally not touched:
- the original sibling project `studentlist`

## Ownership

Hefner Sprach Hub is a proprietary project authored and maintained by Serhii TK.
See `AUTHORS.md`, `NOTICE.md`, and `LICENSE.md` for ownership and review-use
terms.

## Reviewer Quickstart

Use these commands to validate the project from a clean checkout:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm --prefix learning-portal ci
npm --prefix learner-portal ci
npm --prefix instructor-workspace ci
npm --prefix admin-console ci
npm run verify:local
```

The root `package.json` is a convenience entrypoint for checks across the monorepo. It does not replace the individual frontend package files.

Review references:
- Reviewer handoff: [REVIEWER_HANDOFF.md](docs/REVIEWER_HANDOFF.md)
- Professionalization plan: [PROFESSIONALIZATION_PLAN.md](docs/PROFESSIONALIZATION_PLAN.md)
- Review snapshot plan: [REVIEW_SNAPSHOT_PLAN.md](docs/REVIEW_SNAPSHOT_PLAN.md)
- Contributor workflow: [CONTRIBUTING.md](CONTRIBUTING.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

## Local Run

### 1. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_online_data
python manage.py runserver 1212
```

`backend/Studentlist/settings.py` automatically loads variables from `backend/.env`.

### 2. Public frontend

```powershell
cd learning-portal
copy .env.example .env
npm install
npm run dev
```

### 3. Student frontend

```powershell
cd learner-portal
copy .env.example .env
npm install
npm run dev
```

### 4. Teacher frontend

```powershell
cd instructor-workspace
copy .env.example .env
npm install
npm run dev
```

### 5. Admin frontend

```powershell
cd admin-console
copy .env.example .env
npm install
npm run dev
```

Local URLs:
- Backend admin: `http://localhost:1212/admin/`
- Online API: `http://localhost:1212/api/online/`
- Public app: `http://localhost:5182/`
- Student app: `http://localhost:5180/`
- Teacher app: `http://localhost:5183/`
- Admin app: `http://localhost:5184/`

Demo access created in local sqlite:
- Admin: `admin@learning-hub.local` / `AdminPass12345!`
- Teacher: `teacher@learning-hub.local` / `TeacherPass12345!`

Validation commands:

```powershell
npm run backend:check
npm run backend:migrations:check
npm run backend:test
npm run build
npm run compose:config:all
npm run review:check
```

Docker deployment:

```powershell
cd <repo-root>
copy .env.example .env
```

Deployment details:
- Recommended production layout: [DEPLOYMENT_SPLIT_STACK.md](docs/DEPLOYMENT_SPLIT_STACK.md)
- Fallback all-in-one stack: [DEPLOYMENT.md](docs/DEPLOYMENT.md)
- Fallback compose file: [docker-compose.yml](docker-compose.yml)
- GitHub/VPS handoff: [GITHUB_AND_SERVER_CHECKLIST.md](docs/GITHUB_AND_SERVER_CHECKLIST.md)
- Current OVH VPS migration notes: [CURRENT_VPS_MIGRATION.md](docs/CURRENT_VPS_MIGRATION.md)
- Reviewer handoff: [REVIEWER_HANDOFF.md](docs/REVIEWER_HANDOFF.md)
- Professionalization plan: [PROFESSIONALIZATION_PLAN.md](docs/PROFESSIONALIZATION_PLAN.md)
- Review snapshot plan: [REVIEW_SNAPSHOT_PLAN.md](docs/REVIEW_SNAPSHOT_PLAN.md)

Enterprise package:
- Execution roadmap: [ENTERPRISE_PLATFORM_EXECUTION_PLAN.md](docs/ENTERPRISE_PLATFORM_EXECUTION_PLAN.md)
- Catalog/program execution plan: [CATALOG_AND_PROGRAMS_EXECUTION_PLAN.md](docs/CATALOG_AND_PROGRAMS_EXECUTION_PLAN.md)
- Security package: [SECURITY_PACKAGE.md](docs/SECURITY_PACKAGE.md)
- Architecture and data flow: [ARCHITECTURE_AND_DATA_FLOW.md](docs/ARCHITECTURE_AND_DATA_FLOW.md)
- Access matrix: [ACCESS_MATRIX.md](docs/ACCESS_MATRIX.md)
- Retention and recovery policy: [RETENTION_AND_RECOVERY_POLICY.md](docs/RETENTION_AND_RECOVERY_POLICY.md)
- DPA template: [DPA_TEMPLATE.md](docs/DPA_TEMPLATE.md)
- Subprocessors: [SUBPROCESSORS.md](docs/SUBPROCESSORS.md)
- Security review checklist: [SECURITY_REVIEW_CHECKLIST.md](docs/SECURITY_REVIEW_CHECKLIST.md)
- Vendor deck outline: [VENDOR_READY_DECK.md](docs/VENDOR_READY_DECK.md)
- Pilot offer template: [PILOT_OFFER_TEMPLATE.md](docs/PILOT_OFFER_TEMPLATE.md)
- Customer security pack: [CUSTOMER_SECURITY_PACK.md](docs/CUSTOMER_SECURITY_PACK.md)
- Enterprise sales deck: [ENTERPRISE_SALES_DECK.md](docs/ENTERPRISE_SALES_DECK.md)
- Commercial one-pager: [COMMERCIAL_ONE_PAGER.md](docs/COMMERCIAL_ONE_PAGER.md)
- System presentation source: [SYSTEM_PRESENTATION.txt](docs/SYSTEM_PRESENTATION.txt)

One-command style production path after clone:

```bash
bash deploy/server/bootstrap-ubuntu.sh
bash deploy/server/deploy.sh --domain your-domain.example --email admin@your-domain.example
```

## Extraction Notes

- The original `apps.online` code was copied into this project and kept as intact as possible.
- To avoid coupling to the original monolith, this backend provides minimal local replacements for:
  - `apps.users`
  - `apps.employees`
- Management of courses/cohorts/sessions is available through both Django admin and the extracted `admin-console` / `instructor-workspace` workspaces.
- Production deployment is split into an upper infra stack (`nginx + certbot + pgvector + redis + directus + backups`) and a separate app stack (`backend + scheduler + 4 frontends`) connected through a shared Docker network.
