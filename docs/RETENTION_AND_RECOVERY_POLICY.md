# Retention And Recovery Policy

This document defines the default operational policy for backups, restore validation, and data retention for `Learning Hub`.

## 1. Recovery objectives

Recommended default targets for enterprise deployments:

| Metric | Target |
| --- | --- |
| RPO | up to 24 hours |
| RTO | up to 8 business hours for standard recovery |
| Critical route smoke validation | within 30 minutes after restore |

These are default platform targets and can be tightened per customer environment.

## 2. Backup scope

The recovery scope must include:

- application database
- Directus database
- media uploads
- Directus uploads
- Jupyter and notebook runtime data when enabled

Current backup references:

- [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md)

## 3. Backup cadence

Recommended default cadence:

- daily database dump for application DB
- daily database dump for Directus DB
- daily snapshot of mutable file volumes
- weekly restore validation
- quarterly disaster recovery dry run

## 4. Restore order

Recommended full restore order:

1. restore application DB
2. restore Directus DB
3. restore Directus uploads
4. restore application media
5. restore Jupyter data if used
6. restart infra and app stacks
7. rebuild training knowledge index
8. run smoke tests and admin verification

## 5. Data retention categories

Recommended default retention model:

| Data category | Recommended retention | Notes |
| --- | --- | --- |
| Audit events | 12 months minimum | extend for regulated customers |
| Completion evidence | 24 months minimum | often aligned to internal learning policy |
| Attestations | same as completion evidence | retain with course version context |
| Delivery logs | 90 to 180 days | depends on customer observability policy |
| Backups | 30 to 90 days | environment-specific |
| Support or AI queue items | 90 to 180 days | unless customer requires longer retention |

## 6. Deletion and archival expectations

Default expectations:

- learner-facing inactive content can be archived before deletion
- completion evidence should not be deleted as part of routine cleanup
- audit records should be append-only and only expire through policy-based retention
- customer-specific deletion requests should be executed from the primary system of record and logged

## 7. Restore validation checklist

After a restore, confirm:

- `GET /api/health/` returns `200`
- `GET /api/health/ready/` returns ready
- public site loads
- learner workspace loads
- admin workspace loads
- one admin can authenticate
- one learner can authenticate
- course catalog is present
- evidence and governance data are readable

## 8. Disaster recovery drill template

Each quarterly drill should record:

- drill date
- participants
- backup snapshot used
- restore start time
- restore completion time
- smoke-test completion time
- open issues
- remediation owner

## 9. Environment note

This policy is a platform baseline. Enterprise customers may require:

- customer-managed retention periods
- customer-specific backup encryption controls
- customer-specific deletion workflows
- evidence retention for a longer period
