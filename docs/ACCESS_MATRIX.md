# Access Matrix

This matrix describes who can access which product surface and which scoped accountability assignments are available in `Hefner Sprach Hub`.

## 1. Product roles

Primary user-facing roles:

| Role | Purpose | Typical user |
| --- | --- | --- |
| Guest | Public or invited access with minimal rights | external visitor or prospect |
| Student | Learner access to assigned courses and recordings | employee, trainee, cohort learner |
| Instructor | Course delivery and learner support access | trainer, teacher, subject expert |
| Admin | Platform administration and governance access | academy owner, operations lead |

## 2. Admin scoped accountability roles

Sprint 4 introduced scoped accountability assignments:

| Scoped role | Meaning | Scope types |
| --- | --- | --- |
| `manager` | primary accountable owner | academy, course, cohort |
| `delivery_manager` | delivery and session owner | academy, course, cohort |
| `compliance_manager` | evidence, policy, and readiness owner | academy, course, cohort |
| `review_manager` | review and release gate owner | academy, course, cohort |

Supported scope types:

- `academy`
- `course`
- `cohort`

## 3. Surface access matrix

| Surface | Guest | Student | Instructor | Admin |
| --- | --- | --- | --- | --- |
| Public site | Yes | Yes | Yes | Yes |
| Public course pages | Yes | Yes | Yes | Yes |
| Student workspace | No | Yes | Optional, if enrolled | Yes |
| Interactive lesson route | No | Yes | Optional, if enrolled | Yes |
| Teacher workspace | No | No | Yes | Yes |
| Admin Control Plane | No | No | No | Yes |
| Django admin | No | No | No | restricted admin only |

## 4. Operational permissions by function

| Capability | Student | Instructor | Admin |
| --- | --- | --- | --- |
| View enrolled courses | Yes | Optional | Yes |
| Run lesson flow | Yes | Optional | Yes |
| Submit attestation | Yes | No | Yes |
| Review course structure | No | Limited | Yes |
| Publish course | No | No | Yes |
| Assign scoped owners | No | No | Yes |
| View enterprise summary | No | No | Yes |
| Review audit/governance signals | No | Limited | Yes |

## 5. Default access principles

- least privilege by workspace
- accountability separated from learner enrollment
- admin actions are expected to be auditable
- course and cohort ownership can be delegated without granting full platform admin

## 6. Recommended enterprise rollout model

For a typical enterprise deployment:

- learners receive `Student`
- instructors receive `Instructor`
- academy owners receive `Admin`
- accountability is then layered through scoped assignments

Recommended mapping:

- central L&D or academy lead -> `manager` at academy scope
- course owner -> `manager` or `review_manager` at course scope
- delivery lead -> `delivery_manager` at cohort scope
- compliance or QA lead -> `compliance_manager` at course or academy scope

## 7. Notes for customer-facing documents

When presenting the platform externally:

- describe product roles separately from scoped accountability
- do not imply SCIM or JIT provisioning unless enabled in the target tenant
- confirm whether admins are customer-managed or vendor-managed in the offered deployment model
