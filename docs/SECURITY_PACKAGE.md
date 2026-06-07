# Security Package

This package positions `Learning Hub` as a universal enterprise learning platform with governed content, completion evidence, scoped accountability, and operational controls. It is written for technical buyers, security reviewers, and delivery owners across industries, not only for regulated financial teams.

## Package scope

The security package covers:

- product architecture and data flows
- identity and access model
- logging and audit posture
- backup, restore, and retention policy
- incident and recovery expectations
- contractual support documents

Related documents:

- [ARCHITECTURE_AND_DATA_FLOW.md](ARCHITECTURE_AND_DATA_FLOW.md)
- [ACCESS_MATRIX.md](ACCESS_MATRIX.md)
- [RETENTION_AND_RECOVERY_POLICY.md](RETENTION_AND_RECOVERY_POLICY.md)
- [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md)
- [DPA_TEMPLATE.md](DPA_TEMPLATE.md)
- [SUBPROCESSORS.md](SUBPROCESSORS.md)
- [SECURITY_REVIEW_CHECKLIST.md](SECURITY_REVIEW_CHECKLIST.md)

## Product summary

`Learning Hub` is an internal academy and enterprise learning workspace with:

- public catalog and learner access surfaces
- guided lesson flow with theory, concept, video, quiz, practice, and summary
- completion rules, learner attestation, and completion evidence
- governed publishing lifecycle and version history
- scoped accountability for academy, course, and cohort operations
- admin reporting for identity, delivery, governance, and at-risk learners

## Deployment model

The recommended production topology uses:

- TLS termination through `nginx`
- application services on a split Docker stack
- PostgreSQL with `pgvector`
- Redis cache
- Directus content layer
- isolated app frontends for public, learner, teacher, and admin workspaces

Reference:

- [DEPLOYMENT_SPLIT_STACK.md](DEPLOYMENT_SPLIT_STACK.md)

## Security control areas

### 1. Identity and access

Current platform controls:

- local password sign-in
- seeded identity provider registry for:
  - local password
  - Microsoft Entra ID
  - Google Workspace
- scoped accountability assignments for:
  - academy
  - course
  - cohort
- role-aware access surfaces for learner, instructor, and admin use cases

Current status note:

- the identity-provider model and reporting foundation are implemented
- SSO provider records are present and reportable
- full OIDC login activation and SCIM provisioning are still rollout tasks, not active default behavior

### 2. Governance and release control

Current platform controls:

- course lifecycle states: `draft`, `in_review`, `approved`, `published`, `archived`
- approval history
- publish readiness checks
- version snapshots for controlled release

### 3. Completion evidence

Current platform controls:

- course-level completion rules
- learner progress records
- attendance thresholds
- attestation capture
- immutable completion evidence issuance

### 4. Logging and audit

Current platform controls:

- admin and governance mutations emit `OnlineAuditEvent`
- lifecycle and publishing changes are auditable
- reporting layer aggregates exception and governance signals

### 5. Platform operations

Current platform controls:

- health and readiness endpoints
- automated database backups
- documented restore order
- split-stack deployment and smoke-test flow

### 6. Data protection

Current platform controls:

- environment-based secrets configuration
- loopback-only Directus admin exposure by default
- documented backup and restore procedures
- documented retention model and DPA template

## Implementation status snapshot

Status as of `April 4, 2026`:

| Area | Status | Notes |
| --- | --- | --- |
| Split-stack deployment | Active | Production layout documented and deployed |
| Audit events | Active | Governance and admin actions covered |
| Completion evidence | Active | Rule-based completion and attestation implemented |
| Scoped accountability | Active | Academy/course/cohort assignments implemented |
| Identity provider registry | Active | Local password active, enterprise providers modeled |
| OIDC sign-in activation | Planned | Foundation is in place, activation remains a rollout task |
| SCIM provisioning | Planned | Not active yet |
| Formal penetration test | Planned | Not part of this repository |
| SIEM export | Planned | Not part of this repository |

## Recommended buyer-facing message

Use this positioning externally:

`Learning Hub is a secure enterprise learning workspace that combines governed content operations, structured lesson flows, completion evidence, scoped accountability, and operational reporting in one deployable platform.`

Avoid promising:

- active SAML or SCIM if they are not enabled in the target environment
- certifications or third-party attestations that are not yet completed
- customer-specific policies as if they were default product behavior

## Procurement package contents

The minimum enterprise-ready package should include:

- this security package
- architecture and data-flow document
- access matrix
- retention and recovery policy
- DPA template
- subprocessors list
- operations runbook
- vendor deck
- pilot offer

## Internal owner checklist

Before sharing with a customer, confirm:

- deployment topology matches the offered environment
- actual identity provider configuration matches the proposal
- retention periods are aligned with the target customer policy
- subprocessors list is current for the offered environment
- restore validation has been run within the last quarter
