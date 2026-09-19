# UniForge — Phase 1A Foundation

Verified university digital ecosystem. This phase establishes the technical
foundation only: frontend shell, backend API shell, Postgres wiring, and docs.
No business features yet.

## Stack

- Frontend: Next.js 14 (App Router) + TypeScript + Tailwind CSS
- Backend: Python + FastAPI + Pydantic v2 + SQLAlchemy 2.0
- Database: PostgreSQL 15 (via Docker Compose locally, RDS Free Tier in AWS)
- Shape: modular monolith, simple REST, server-side pagination (later)

See `docs/architecture.md` for the full architecture and decisions.

## Prerequisites

- Python 3.12+
- Node 20+
- Docker (for Postgres)

## Quick start

```bash
# 1. Postgres
docker compose up -d db

# 2. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
# health: http://localhost:8000/api/v1/health
# readiness (includes DB): http://localhost:8000/api/v1/ready

# 3. Frontend (new terminal)
cd frontend
npm install
cp .env.example .env.local
npm run dev
# app: http://localhost:3000
# connectivity page: http://localhost:3000/health
```

## Tests / checks

```bash
# backend
cd backend && source .venv/bin/activate && pytest -q

# frontend
cd frontend && npm run typecheck && npm run build
```

## Error envelope

All API errors use:

```json
{ "error": { "code": "MACHINE_CODE", "message": "human message", "details": null } }
```

Codes: `NOT_FOUND`, `VALIDATION_ERROR` (422), `HTTP_ERROR`, `INTERNAL_ERROR`.
Domain errors in later phases will follow the same envelope via `AppError`.

## Project layout

```
backend/app/{core,api/v1,db}  # config, errors, routers, SQLAlchemy base/session
backend/tests/                # pytest
frontend/app/                 # App Router pages (/, /health)
frontend/{components,lib}/    # ApiStatus, typed API client
docs/architecture.md          # system, DB, auth placeholder, graph, AWS
docker-compose.yml            # local Postgres
```
