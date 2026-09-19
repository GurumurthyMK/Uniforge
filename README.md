# UniForge — Phase 1B Identity & Authentication

Verified university digital ecosystem: university structure, verified
university identity (separate from student-controlled profile), session auth,
and role-based server-side authorization.

## Stack

- Frontend: Next.js 14 (App Router) + TypeScript + Tailwind CSS
- Backend: Python + FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic
- Database: PostgreSQL 16 (via Docker Compose locally, RDS Free Tier in AWS)
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
alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload --port 8000
# health: http://localhost:8000/api/v1/health
# readiness (includes DB): http://localhost:8000/api/v1/ready

# 3. Frontend (new terminal)
cd frontend
npm install
cp .env.example .env.local
npm run dev
# app: http://localhost:3000  (register, login, authenticated shell at /app)
```

## Demo flow (register → verified → shell)

1. Open http://localhost:3000/register
2. Pick "Demo University", any class, a student number, enrollment code
   `UNIFORGE-DEMO-2026`, and a `@demo-university.edu` email → identity is
   VERIFIED instantly. Any mismatch → PENDING, an admin approves it.
3. You land on `/app`: academic breadcrumb, verified university identity
   (locked, read-only) next to your editable student profile.
4. Explore `/app/profile` (full profile), `/app/profile/edit` (headline, bio,
   links, skills, interests, hobbies), `/app/class` (classmates), and
   `/app/people/<id>` (public profiles). Admins get `/app/admin` for the
   academic hierarchy.

Or skip registration: log in as `ada@demo-university.edu` / `Demo1234!`.
All seeded users share the password `Demo1234!` (see `backend/app/db/seed.py`
for the full list incl. admin, class rep, faculty, staff).

## Tests / checks

```bash
# backend (SQLite, no Postgres needed)
cd backend && source .venv/bin/activate && pytest -q

# frontend
cd frontend && npm run typecheck && npm run build
```

## Error envelope

All API errors use:

```json
{ "error": { "code": "MACHINE_CODE", "message": "human message", "details": null } }
```

Codes: `NOT_FOUND`, `VALIDATION_ERROR` (422), `HTTP_ERROR`, `AUTH_FAILED`
(401), `FORBIDDEN` (403), `CONFLICT` (409), `INTERNAL_ERROR`.

## Project layout

```
backend/app/{core,api/v1,db,modules/identity,modules/profile}
backend/alembic/                                # migrations (reviewed as code)
backend/tests/                                  # pytest (health + auth + profile)
frontend/app/                                   # /, /health, /login, /register, /app/...
frontend/{components,lib}/                      # cards, api client, auth
frontend/middleware.ts                          # UX gate for /app (API authorizes)
docs/architecture.md                            # system, DB, auth, graph, AWS
docker-compose.yml                              # local Postgres
```
