# UniForge Architecture (MVP — Phase 1A)

## 1. System architecture

Modular monolith, AWS Free Tier compatible. One deployable backend, one
frontend, one relational database. No microservices, no Kubernetes, no Kafka,
no Redis, no dedicated graph database in the MVP.

```
Browser
  └─ Next.js 14 frontend (SSR + client components)
       │  REST/JSON over HTTPS
       ▼
     FastAPI backend (modular monolith)
       ├─ app/api/v1/*      versioned REST routers (one module per domain later)
       ├─ app/core/*        config, error envelope, (auth later)
       ├─ app/db/*          engine/session/Base, Alembic migrations (later)
       └─ domain services   (Phase 1B+: identity, profile, spaces, graph)
            │
            ▼
     PostgreSQL 15 (relational system of record)
     S3 (later, only for file attachments in posts)
```

Local dev mirrors prod shape: `docker-compose.yml` runs Postgres; the API and
web app run natively (`uvicorn --reload`, `next dev`).

## 2. Frontend / backend responsibilities

Frontend (Next.js App Router, TypeScript, Tailwind):

- Server Components for data display with server-side pagination.
- Client components only where interactivity requires it (e.g. `ApiStatus`).
- Typed API client in `frontend/lib/api.ts`; no business logic duplication.
- Respects backend error envelope (`{error: {code, message, details}}`).
- Never enforces authorization; renders what the API authorizes.

Backend (FastAPI, Pydantic, SQLAlchemy):

- Versioned REST under `/api/v1`; Pydantic validates all external input.
- Shared error handlers produce the standard envelope (see `app/core/errors.py`).
- SQLAlchemy 2.0 is the only persistence abstraction; Alembic for migrations
  (introduced with the first domain tables in Phase 1B).
- Stateless API: no in-memory sessions; auth will be token-based (see §4).
- Bounded queries: every list endpoint will be paginated (`limit ≤ 100`).

## 3. Database strategy

PostgreSQL is the system of record for all core entities (University,
Department, Program, Batch, Class, User, Profile, Skill, Interest, Club,
Forum, ForumMember, Post, Comment, Connection, Notification).

- Official academic data (university-controlled/verified) and personal profile
  data (student-controlled) are separate tables/columns by design — enforced in
  the service layer and at the API boundary, not just in the UI.
- Migrations via Alembic, reviewed as code; no ad-hoc DDL.
- Files/links live in posts as metadata; binary content goes to S3 (presigned
  URLs), never in Postgres bytea.
- Local: `docker compose up -d db` (postgres:16-alpine + `pgdata` volume).
- AWS: RDS PostgreSQL (db.t3.micro, Free Tier) + automated snapshots.

## 4. Authentication & identity (implemented in 1B)

- Passwords: Argon2id (`argon2-cffi`); rehashed on login when parameters change.
- Sessions: opaque `secrets.token_urlsafe` tokens, SHA-256-hashed at rest in
  `sessions`, 7-day expiry (`SESSION_EXPIRE_DAYS`), immediate revoke on logout.
  Clients send `Authorization: Bearer`. No JWTs (revocation is trivial).
- Verification (demo-honest, no fake ERP): registration supplies university +
  class + student_no + enrollment code. The identity becomes VERIFIED only if
  the class belongs to the university (chain validated server-side), the email
  domain matches the university, the enrollment code verifies, and the
  student_no is free. Otherwise PENDING for admin review
  (`GET/PATCH /admin/identities`, restricted to verified UNIVERSITY_ADMIN /
  DEPARTMENT_ADMIN of that university — enforced in the service layer).
- Roles (`Role` enum on `UniversityIdentity`): UNIVERSITY_ADMIN,
  DEPARTMENT_ADMIN, FACULTY, STAFF, CLASS_REP, STUDENT. Registration always
  creates STUDENT; promotion is admin-only. Class reps resolve via
  identity(role=CLASS_REP, class_id=X) — no circular FK.
- Identity vs profile: `UniversityIdentity` rows are read-only for students
  (no PATCH endpoint exists); `Profile` is patched by the owner via
  `PATCH /auth/profile`. The `/app` dashboard renders them as separate cards.
- Frontend: token in localStorage + readable `uf_token` cookie; Next.js
  middleware gates `/app/*` for UX only. Every protected API call is
  re-authorized server-side per request.
- Demo data: `python -m app.db.seed` (idempotent). All demo passwords
  `Demo1234!`; enrollment code `UNIFORGE-DEMO-2026`. Upgrade path: HttpOnly
  cookies + refresh rotation; real ERP via roster import into a new
  `enrollment_roster` table without touching this model.

## 5. Graph strategy (derived from relational data — no graph DB)

The network graph and talent graph are query/domain layers over relational
tables, not separate infrastructure.

- Network graph: heterogeneous projection over joins between Student, Class,
  Club, Forum, Project, Skill, Interest. MVP exposes student-centered
  ego-graphs (e.g. "my classes/clubs/forums/connections"), bounded to depth 1–2
  with pagination. Kept in SQL (`JOIN` + recursive CTEs only where needed).
- Talent graph: bipartite projection Student↔Skill / Student↔Interest (+
  Hobby as an `Interest.kind`). Manual add/import writes the same edge tables,
  so future evidence/import pipelines (e.g. "added from project X") only add a
  `source` column / edge table, never a redesign.
- Later scale path (documented, not built): materialized similarity views →
  background recompute job → (only if proven necessary) a dedicated graph store.

Deliberately not built in 1A: similarity scoring, recommendations, PageRank.

## 6. AWS deployment strategy (Free Tier, smallest reliable shape)

- Compute: single EC2 t3.micro (or ECS Fargate spot-equivalent) running two
  containers/processes: `web` (Next.js standalone) + `api` (uvicorn). One ALB
  or single-instance Nginx in front; `/api/*` → backend, `/` → frontend.
- Database: RDS PostgreSQL db.t3.micro (Free Tier, 20 GB gp2, backups on).
- Storage: S3 Standard for attachments (later phase); CloudFront optional.
- Config: SSM Parameter Store for secrets; env vars for non-secrets.
- CI: GitHub Actions — `pytest`, `tsc`, `next build`, then Docker build/push.
- Cost guards: no NAT Gateway (single public subnet), no OpenSearch, no
  ElastiCache, no MSK, minimal CloudWatch retention.

## 7. Important architectural decisions

| # | Decision | Rationale | Revisit when |
|---|----------|-----------|--------------|
| 1 | Modular monolith over microservices | One team, Free Tier budget, MVP speed | Sustained team/scale pain |
| 2 | Postgres only; graph as domain layer | Avoids Neptune/Neptune cost + ops; relational joins cover MVP ego-graphs | Proven multi-hop latency at scale |
| 3 | FastAPI + SQLAlchemy 2.0 | Strong typing via Pydantic, mature, small footprint | — |
| 4 | Next.js App Router + server pagination | Cheap SSR, less client state, natural page-based limits | — |
| 5 | Error envelope `{error:{code,message,details}}` | Uniform client handling from day one | — |
| 6 | `/health` (liveness) + `/ready` (DB check) | ALB target groups + deploy safety | — |
| 7 | No Redis/Kafka/S3 in 1A | No MVP requirement needs them yet | Feeds/notifications scale, file uploads |
| 8 | Academic vs profile data separation (by design) | Core product rule: verified vs student-controlled | Phase 1B schema |

## 8. Phase 1A verification

- `GET /api/v1/health` → `{"status":"ok","service":"uniforge-api","version":"0.1.0"}`
- `GET /api/v1/ready` → `{"status":"ok|degraded","database":"up|down"}`
- `/` renders the shell; `/health` shows live backend JSON; `ApiStatus`
  component reports connected/unreachable without crashing.
- `pytest -q` passes; `tsc --noEmit` and `next build` pass.
