# Directus Training Setup

This document defines the Directus-side production wiring for `Learning Hub`.

## Required purpose

Directus is used for:
- email flows
- course-access email flow
- training content authoring and publish/unpublish sync into `TrainingContentItem`

## Required secrets

In `.env`:
- `ONLINE_EMAIL_DIRECTUS_FLOW_URL`
- `ONLINE_COURSE_ACCESS_DIRECTUS_FLOW_URL`
- `ONLINE_EMAIL_DIRECTUS_TOKEN`
- `TRAINING_DIRECTUS_SYNC_TOKEN`

For the packaged demo stack:
- Directus email transport is wired to `Mailpit`
- webhook email flows are provisioned by [setup_directus_communications.py](deploy/directus/setup_directus_communications.py)
- training authoring sync is provisioned by [setup_training_directus.py](deploy/directus/setup_training_directus.py)

## Training content sync endpoint

Endpoint:
```text
POST https://<your-domain>/api/training/internal/directus/content-sync/
```

Header:
```text
Authorization: Bearer <TRAINING_DIRECTUS_SYNC_TOKEN>
Content-Type: application/json
```

## Expected payload

Reference examples:
- [training-content-sync.upsert.example.json](deploy/directus/training-content-sync.upsert.example.json)
- [training-content-sync.delete.example.json](deploy/directus/training-content-sync.delete.example.json)

Minimal published upsert:
```json
{
  "operation": "upsert",
  "externalId": "directus-item-id",
  "slug": "directus-cva-primer",
  "name": "Directus CVA Primer",
  "description": "Synced from Directus.",
  "bodyMarkdown": "## CVA\\nCVA represents expected credit adjustment over the life of a trade.",
  "contentKind": "article",
  "status": "published",
  "accessScope": "entitled",
  "courseSlug": "directus-sync-course",
  "ownerEmail": "owner@example.com",
  "assetClasses": [{"slug": "credit", "name": "Credit"}],
  "topics": ["cva"],
  "audienceSlugs": ["institutional-skills"],
  "crossReferences": [{"slug": "reference-faq", "relationType": "related"}]
}
```

Delete/unpublish:
```json
{
  "operation": "delete",
  "externalId": "directus-item-id",
  "slug": "directus-cva-primer"
}
```

## Behavior

Published content:
- upserts `TrainingContentItem`
- updates taxonomy and cross-references
- rebuilds the knowledge index
- records `TrainingContentSyncEvent`
- records `TrainingAuditEvent` with `directus.sync_applied`

Draft/review/retired content:
- keeps the row
- deactivates indexed chunks
- records unpublish/deactivation in sync/audit ledgers

Delete:
- requires stable `externalId`
- retires the local row instead of hard-delete

Safety rules already enforced by backend:
- Directus cannot overwrite manually managed content by `slug` only
- unknown course/owner/audience values are rejected
- sync endpoint is token-protected and rate-limited

## Directus flow recommendation

Recommended Flow name:
```text
training-content-sync
```

Communication flow names:
```text
online-email
course-access
```

Recommended trigger:
- item create
- item update
- item delete or explicit publish-state change

Recommended action:
- webhook / HTTP request to `/api/training/internal/directus/content-sync/`

Recommended mapping:
- Directus primary key -> `externalId`
- slug -> `slug`
- title/name -> `name`
- markdown body -> `bodyMarkdown`
- workflow status -> `status`
- asset class relation -> `assetClasses`
- topic relation -> `topics`
- audience relation -> `audienceSlugs`

## Recovery path

If a Directus flow failed and content was fixed manually:
```bash
docker compose -f deploy/app/docker-compose.yml --env-file .env exec backend \
  python manage.py rebuild_training_knowledge_index
```

Audit/debug places:
- Django admin `TrainingContentSyncEvent`
- Django admin `TrainingAuditEvent`
- Directus flow activity log

## Recovery access

Directus host port is loopback-only by default:
```text
DIRECTUS_HTTP_BIND=127.0.0.1
```

Use SSH tunneling for admin/recovery access:
```bash
ssh -L 8055:127.0.0.1:8055 ubuntu@your-server-ip
ssh -L 8025:127.0.0.1:8025 ubuntu@your-server-ip
```
