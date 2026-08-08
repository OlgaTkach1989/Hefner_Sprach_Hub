# Architecture And Data Flow

This document describes the platform architecture and the main operational data paths for `Hefner Sprach Hub`.

## 1. System architecture

```mermaid
flowchart LR
    User[Enterprise user] --> Nginx[nginx + TLS]
    Nginx --> Public[learning-portal]
    Nginx --> Student[learner-portal]
    Nginx --> Teacher[instructor-workspace]
    Nginx --> Admin[admin-console]
    Nginx --> API[Django backend]
    API --> DB[(PostgreSQL + pgvector)]
    API --> Redis[(Redis)]
    API --> Directus[Directus]
    API --> Scheduler[Scheduler]
    API --> Grader[Training grader]
    API --> Jupyter[JupyterHub]
    Directus --> DB
    Scheduler --> API
```

## 2. Production stack layout

Upper infra stack:

- `nginx`
- `certbot`
- `postgres`
- `redis`
- `directus`
- backup jobs

App stack:

- `backend`
- `scheduler`
- `traininggrader`
- `jupyterhub`
- `learning-portal`
- `learner-portal`
- `instructor-workspace`
- `admin-console`

Reference:

- [DEPLOYMENT_SPLIT_STACK.md](DEPLOYMENT_SPLIT_STACK.md)

## 3. Identity and access flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant IdentityRegistry as Identity provider registry

    User->>Frontend: Open login surface
    Frontend->>Backend: Authenticate
    Backend->>IdentityRegistry: Resolve enabled provider
    Backend-->>Frontend: Session/JWT claims
    Frontend-->>User: Workspace access by role and scope
```

Current implementation:

- local password sign-in is active
- identity providers are modeled as first-class records
- provider readiness is surfaced in admin reporting
- Microsoft Entra and Google Workspace are represented as activation-ready providers

## 4. Content governance flow

```mermaid
sequenceDiagram
    participant Author
    participant AdminUI as Admin Control Plane
    participant Backend
    participant Audit as Audit events

    Author->>AdminUI: Edit course draft
    AdminUI->>Backend: Save course changes
    Backend->>Audit: Record update event
    Author->>AdminUI: Move to in_review
    AdminUI->>Backend: Request lifecycle transition
    Backend->>Audit: Record lifecycle event
    Backend-->>AdminUI: Readiness status and version snapshot
```

## 5. Learner completion and evidence flow

```mermaid
sequenceDiagram
    participant Learner
    participant StudentUI as Student Workspace
    participant Backend
    participant Evidence as Completion evidence

    Learner->>StudentUI: Complete lesson steps
    StudentUI->>Backend: Persist lesson progress
    Backend-->>StudentUI: Updated completion summary
    Learner->>StudentUI: Confirm attestation
    StudentUI->>Backend: Submit attestation
    Backend->>Evidence: Issue immutable evidence record
    Backend-->>StudentUI: Completed status
```

## 6. Data categories

Primary operational data:

- user and profile identity data
- course, module, lesson, and section content
- cohort, schedule, and attendance data
- learner progress and completion evidence
- audit and governance records
- AI and knowledge operations metadata

Supporting data:

- media assets
- recordings and resource links
- Directus sync metadata
- background job telemetry

## 7. Trust boundaries

Boundary 1: public internet to `nginx`

- TLS termination
- route separation by surface

Boundary 2: frontend surfaces to backend API

- authenticated requests
- role-based workspace access

Boundary 3: backend to infrastructure services

- database
- cache
- Directus
- background services

Boundary 4: optional external service integrations

- Microsoft Teams / Outlook / Planner links
- optional AI provider
- optional identity provider activation

## 8. Security-sensitive components

Security-sensitive components include:

- Django backend
- PostgreSQL database
- Directus content plane
- identity provider settings
- Jupyter and grader runtime controls
- audit and completion evidence records

## 9. Recommended diagram usage

Use this document:

- in security review packages
- during technical due diligence
- inside pilot proposals for enterprise customers
- as the architecture section of the vendor deck
