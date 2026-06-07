# Catalog, Profiles, Programs, and Knowledge Plan

This plan translates the customer's requests into an additive roadmap on top of the current `Learning Hub` platform.

## Product Goal

Evolve the system from a course delivery platform into a reusable enterprise learning platform with:

- governed internal and external course catalog
- configurable metadata for courses and people
- searchable student, instructor, and course registries
- programmable learning paths and assignments
- AI-assisted authoring and recommendations
- knowledge base ingestion and retrieval

## Guiding Rules

- keep current course delivery, lesson flow, and admin surfaces working
- add new metadata and program logic without breaking existing demo data
- unify internal and third-party courses under one searchable catalog
- separate identity, people registry, content catalog, and knowledge assets

## Workstreams

### 1. Catalog Foundation

Add standard metadata for courses:

- provider and origin
- confidentiality level
- knowledge domain
- course type and delivery model
- difficulty level
- duration, rating, and recommendation flags
- target audience, tags, and skills
- custom configurable fields

### 2. People Registry

Extend student and instructor records:

- student employment and organizational fields
- instructor authoring and expertise profile
- distinct visibility rules for admins, instructors, and managers

### 3. Access and Search

Add:

- richer search filters
- catalog search endpoint
- permission-aware search results
- configurable metadata definitions

### 4. Programs and Assignments

Add:

- reusable learning programs
- program-to-course items
- student program assignments
- support for manual, role-based, and AI-assisted assignment sources

### 5. External Courses and Knowledge Base

Add:

- external course provider registry
- course linking to third-party catalogs
- knowledge source and document registry
- ingestion-ready document metadata for AI and search

## Execution Order

1. backend models and migrations
2. backend serializers, services, and admin endpoints
3. admin course builder metadata expansion
4. admin registry and program management UI
5. verification through migrations, tests, and builds

## Verification Targets

- migrations apply cleanly on the current database
- current course builder and lesson flow remain unchanged
- admin course list and detail return new metadata
- student and instructor registries expose new profile data
- catalog search returns filtered results across internal and external items
- programs and knowledge sources can be created through admin APIs
