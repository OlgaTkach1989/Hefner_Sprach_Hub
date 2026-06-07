# Customer Security Pack

Prepared for enterprise customers evaluating `Learning Hub` as a secure internal academy and enterprise learning workspace.

Version:

- `April 5, 2026`

## 1. Executive summary

`Learning Hub` is a deployable enterprise learning platform built for:

- onboarding
- role-based upskilling
- internal knowledge transfer
- cohort-based delivery
- compliance-ready learning flows

The platform combines:

- public learning discovery
- structured learner workspaces
- instructor and delivery surfaces
- governed content operations
- completion evidence and attestation
- scoped accountability and reporting

## 2. Product architecture

The recommended production deployment uses:

- `nginx` for TLS termination
- split infrastructure and application stacks
- Django backend
- PostgreSQL with `pgvector`
- Redis
- Directus content services
- isolated frontends for public, learner, teacher, and admin workspaces

Reference detail:

- [ARCHITECTURE_AND_DATA_FLOW.md](ARCHITECTURE_AND_DATA_FLOW.md)

## 3. Access and identity model

Current platform controls:

- local password sign-in
- modeled identity-provider registry
- provider readiness reporting
- role-aware workspace access
- scoped accountability assignments for:
  - academy
  - course
  - cohort

Current identity-provider foundation includes:

- local password
- Microsoft Entra ID
- Google Workspace

Status note:

- provider modeling and readiness reporting are implemented
- enterprise SSO activation is deployment-dependent
- SCIM provisioning is not part of the active default deployment

## 4. Governance and release control

The content model is governed through:

- lifecycle states:
  - `draft`
  - `in_review`
  - `approved`
  - `published`
  - `archived`
- approval history
- version snapshots
- release readiness checks before publish

This allows content owners to separate authoring from release control.

## 5. Completion evidence

The platform supports formal evidence of learning through:

- completion rules
- lesson and course progress tracking
- attendance thresholds
- learner attestation
- immutable completion evidence issuance

This makes the platform usable for structured internal learning programs where completion must be visible and reviewable.

## 6. Logging and auditability

Governance and admin actions are captured through audit events. The reporting layer can surface:

- governance exceptions
- delivery issues
- scope and accountability assignments
- at-risk learners
- content and operational signals

## 7. Backup and restore posture

The platform includes:

- automated database backup jobs
- documented restore order
- smoke-test driven recovery validation
- documented retention and recovery baseline

Reference detail:

- [RETENTION_AND_RECOVERY_POLICY.md](RETENTION_AND_RECOVERY_POLICY.md)
- [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md)

## 8. Customer-facing security status

| Area | Current status |
| --- | --- |
| Split-stack deployment | Active |
| Lifecycle governance | Active |
| Audit event foundation | Active |
| Completion evidence | Active |
| Scoped accountability | Active |
| Identity provider registry | Active |
| OIDC activation | Deployment option |
| SCIM provisioning | Planned extension |

## 9. Data protection package

The enterprise documentation pack includes:

- security package
- architecture and data flow
- access matrix
- retention and recovery policy
- DPA template
- subprocessors list
- security review checklist

## 10. Shared responsibility model

Vendor responsibilities typically include:

- application code and release operation
- deployment procedures
- backup and restore procedures
- product documentation
- issue remediation and support

Customer responsibilities typically include:

- approved user population
- identity and access policies
- content governance ownership
- retention policy decisions
- legal review of DPA and procurement requirements

## 11. Recommended next step

The recommended commercial next step is a paid pilot with:

- `1` business unit or academy
- `100-300` learners
- `2-3` learning tracks
- `6-8` weeks

Pilot reference:

- [PILOT_OFFER_TEMPLATE.md](PILOT_OFFER_TEMPLATE.md)

## 12. Supporting documents

- [SECURITY_PACKAGE.md](SECURITY_PACKAGE.md)
- [ARCHITECTURE_AND_DATA_FLOW.md](ARCHITECTURE_AND_DATA_FLOW.md)
- [ACCESS_MATRIX.md](ACCESS_MATRIX.md)
- [RETENTION_AND_RECOVERY_POLICY.md](RETENTION_AND_RECOVERY_POLICY.md)
- [DPA_TEMPLATE.md](DPA_TEMPLATE.md)
- [SUBPROCESSORS.md](SUBPROCESSORS.md)
