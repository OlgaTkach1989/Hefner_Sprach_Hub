# AI Assistant Demo

## What is implemented

- Policy-aware knowledge indexing on top of `apps.training`
- Student-facing AI assistant inside `learner-portal` training module
- Source citations limited to visible training content
- Quiz generation and server-side quiz checking
- Audit events for AI ask, response, escalation, quiz generation, and quiz submit
- PostgreSQL `pgvector` hook in migration `training.0006` with SQLite-safe fallback

## Main endpoints

- `GET /api/training/ai/conversation/?content=<slug>`
- `POST /api/training/ai/ask/`
- `POST /api/training/ai/quizzes/generate/`
- `POST /api/training/ai/quizzes/<quiz_public_id>/submit/`

## Provider modes

- `TRAINING_AI_PROVIDER=demo`
  - No external API key required
  - Deterministic extractive answers and quiz generation
- `TRAINING_AI_PROVIDER=openai-compatible`
  - Requires `TRAINING_AI_BASE_URL`, `TRAINING_AI_API_KEY`, `TRAINING_AI_CHAT_MODEL`
  - Uses an OpenAI-compatible `chat/completions` endpoint

## Course Builder AI orchestration

Course Builder keeps its legacy lesson-generation path as the default production-safe baseline:

- `COURSE_BUILDER_AI_ORCHESTRATOR=legacy`
  - Uses the existing `TrainingAiProvider` path when `TRAINING_AI_ENABLED=1`
  - Falls back to the deterministic structured template if AI is disabled or unavailable
- `COURSE_BUILDER_AI_ORCHESTRATOR=agents`
  - Uses the OpenAI Agents SDK for lesson draft orchestration
  - Requires `TRAINING_AI_API_KEY` and `TRAINING_AI_CHAT_MODEL`
  - Returns the same Course Builder document shape as the legacy path
  - Falls back to the legacy provider path if the Agents SDK run fails

Agent tracing is disabled by default. Enable it only for controlled debugging with:

```powershell
COURSE_BUILDER_AI_AGENTS_TRACING_ENABLED=1
```

## Demo seed

Create the module described in the local AI brief:

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py seed_training_ai_demo --student-email admin@learning-hub.local
```

This seeds:

- `Fundamentals of Investment Analysis`
- `Investment Analysis FAQ`
- `Investment Analysis Quiz Prep`

## Rebuild knowledge index

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py rebuild_training_knowledge_index
```

Optional filters:

```powershell
.\.venv\Scripts\python.exe manage.py rebuild_training_knowledge_index --slug fundamentals-of-investment-analysis
.\.venv\Scripts\python.exe manage.py rebuild_training_knowledge_index --course investment-analysis-demo
```

## Security notes

- AI endpoints require authenticated users
- Retrieval is scoped to visible `TrainingContentItem` records only
- Hidden cross-references are excluded from citations
- AI endpoints are throttled with dedicated DRF scopes
- Quiz scoring is server-side only
