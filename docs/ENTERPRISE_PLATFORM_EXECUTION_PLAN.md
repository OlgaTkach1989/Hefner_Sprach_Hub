# Enterprise Platform Execution Plan

This roadmap keeps the product positioned as a universal advanced learning platform for enterprise teams, not as a bank-only system. Regulated organizations remain a strong fit, but the implementation targets broad enterprise needs: governed learning flows, evidence of completion, enterprise identity, operational visibility, and controlled publishing.

## Product Target

The platform should evolve into an:

- Enterprise Learning Workspace
- Internal Academy Platform
- Secure Learning and Knowledge Platform

Core scenarios:

- onboarding
- role-based upskilling
- technical learning
- blended cohort delivery
- compliance-ready learning
- internal knowledge transfer

## Delivery Principles

- Keep the existing multi-surface product model: public, learner, teacher, admin, backend.
- Add enterprise controls as reusable platform capabilities, not bank-specific screens.
- Prefer additive changes that preserve current demo and course delivery flows.
- Build every new capability with API contract, UI surface, and operational verification.

## Sprint 1: Governance Foundation

Goal: move from simple publish booleans to governed course lifecycle and auditable admin actions.

Scope:

- add course lifecycle states: `draft`, `in_review`, `approved`, `published`, `archived`
- add approval history records
- add unified audit events for course create/update/lifecycle changes
- expose governance payloads in admin course APIs
- surface lifecycle state in admin course builder and course directory

Verification:

- backend tests for lifecycle transitions and governance payloads
- admin build passes
- backend checks and migrations pass

## Sprint 2: Completion Evidence Layer

Goal: make learning completion provable, exportable, and reusable across industries.

Scope:

- completion rule engine per course
- learner attestation step after summary
- immutable completion evidence records
- downloadable completion/evidence PDF
- learner transcript and admin evidence views

Verification:

- backend tests for completion rules and evidence creation
- learner flow test from lesson completion to evidence generation
- export validation for PDF and CSV evidence

## Sprint 3: Approval Workflow and Versioning

Goal: move content operations from editable live objects to controlled releases.

Scope:

- course and lesson versioning
- workflow roles: author, reviewer, approver, publisher
- release readiness checks before publish
- review queue in admin
- change log and rollback-friendly version history

Verification:

- approval transition tests
- publish gate tests
- admin workflow smoke tests

## Sprint 4: Identity, Managers, and Reporting

Goal: make the platform operationally usable for enterprise rollout.

Scope:

- Microsoft Entra / OIDC SSO
- RBAC with scope: organization, workspace, course, cohort
- manager dashboards
- compliance and delivery reports
- scheduled exports and report snapshots

Verification:

- SSO login flow
- scoped access tests
- report aggregation tests
- dashboard and export smoke tests

## Sprint 5: Security Package and Commercial Readiness

Goal: make the platform procurement-ready for enterprise customers.

Scope:

- architecture and data flow diagrams
- hosting, backup, restore, retention, and incident runbooks
- access matrix and secrets management note
- DPA template and subprocessors list
- vendor-ready deck and pilot offer

Verification:

- disaster recovery dry run
- backup restore validation
- documentation review checklist

## Implementation Progress

Completed:

- Sprint 1: governance foundation
- Sprint 2: completion evidence layer
- Sprint 3: approval workflow and versioning
- Sprint 4: identity foundation, scoped accountability, and enterprise summary reporting
- Sprint 5: security package and commercial readiness documents

## Current Deliverables

The repository now includes:

- governed course lifecycle and version history
- learner attestation and completion evidence
- scoped accountability for academy, course, and cohort
- enterprise summary reporting in admin
- security and procurement documentation package:
  - `SECURITY_PACKAGE.md`
  - `ARCHITECTURE_AND_DATA_FLOW.md`
  - `ACCESS_MATRIX.md`
  - `RETENTION_AND_RECOVERY_POLICY.md`
  - `DPA_TEMPLATE.md`
  - `SUBPROCESSORS.md`
  - `SECURITY_REVIEW_CHECKLIST.md`
  - `VENDOR_READY_DECK.md`
  - `PILOT_OFFER_TEMPLATE.md`
