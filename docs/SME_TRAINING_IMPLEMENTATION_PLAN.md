# SME Training Implementation Plan

## Objective

Extend `Hefner Sprach Hub` from an online lessons platform into an enterprise training platform for quant and core-strats education without destabilizing existing production flows.

## Design Principles

- Keep `apps.online` as the LMS/control-plane for catalog, cohorts, sessions, orders, attendance, and support.
- Add new enterprise learning capabilities in sibling domains, starting with `apps.training`.
- Enforce access only in backend services. Frontend and Directus can assist authoring and UX, but must not be the source of truth for entitlements.
- Treat notebook execution as a separate execution plane. The LMS issues short-lived launch authority; the runtime executes.

## Phase 1: Foundation

- Add `apps.training` with:
  - metadata taxonomy: `TrainingAssetClass`, `TrainingTopic`
  - audience and entitlements: `TrainingAudience`, `TrainingUserAudienceGrant`
  - course governance: `TrainingCourseRoleAssignment`
  - knowledge/content graph: `TrainingContentItem`, `TrainingContentCrossReference`
  - notebook/grader contracts: `TrainingNotebookLabProfile`
- Add entitlement-aware read APIs:
  - `/api/training/content/`
  - `/api/training/content/<slug>/`
  - `/api/training/me/entitlements/`
- Add tests for:
  - internal vs external audience access
  - `ALL` vs `ANY` audience matching
  - notebook contract exposure only to entitled users

## Phase 2: LMS Integration

- Surface entitled content in student UX near sessions/recordings/materials.
- Add course-owner management workflows in admin/staff UX.
- Add completeness checks:
  - missing asset class
  - missing topic
  - missing course owner
  - missing entitlement policy for internal content
- Add audit events for access denials and content lookups.

## Phase 3: Knowledge Base and AI

- Add knowledge article authoring workflow in Directus or Django admin with publishing states.
- Introduce pgvector-backed retrieval and chunk indexing for approved content only.
- Add policy-aware AI assistant:
  - answer only from visible content
  - cite source content items
  - route unresolved questions to course owner/support
- Add FAQ coverage and unresolved-question analytics.

## Phase 4: Notebook Runtime and Auto-Grading

- Introduce JupyterHub as a separate execution plane.
- Use short-lived launch tokens issued by backend.
- Start with runtime contract integration before real spawning.
- Add auto-grader integration path:
  - nbgrader or Otter-Grader compatible profile
  - hidden tests and results storage
  - submission audit trail

## Security Requirements

- No entitlement decisions in frontend.
- No direct notebook access without a backend-issued launch contract.
- No Docker socket exposure to Django backend.
- Notebook containers must run without privileged mode and with explicit resource limits.
- Public endpoints must keep explicit permission declarations and avoid accidental inheritance from permissive defaults.

## Near-Term Next Steps

1. Integrate entitled content into student dashboard and admin governance views.
2. Add audit models/events for content access and lab launch attempts.
3. Add launch-token service and JupyterHub proxy route contract.
4. Add staff CRUD APIs for entitlements and course ownership.
