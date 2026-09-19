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

## 9. Profile domain (implemented in 2A)
Two concepts, enforced at every layer — never merged:

| | VERIFIED UNIVERSITY IDENTITY | STUDENT-CONTROLLED PROFILE |
|---|---|---|
| Source | university records / admin approval | the student |
| Tables | universities, departments, programs, batches, classes, university_identities | profiles, skills, interests, profile_skills, profile_interests |
| Fields | name, university, student_no, dept/program/batch/class, role, status, photo_url | headline, bio, avatar_url, links, career/research interests, skill/interest edges |
| Write path | demo verification flow or admin API only | `PATCH /profile/me` (owner only) |
| Read path | `/auth/me`, identity cards (read-only UI) | own full view, public view for same-university verified users |

- Protection is structural: `ProfileEditIn` uses `extra="forbid"`, so verified
  fields sent to the profile endpoint are rejected with 422; no code path
  writes identity columns from student input. Public profiles exclude email
  and student_no; cross-university access is 403 (checked server-side from the
  caller's verified identities).
- Skills/interests are a canonical catalog (normalized lowercase, unique) plus
  edge tables with a `source` column (`manual` today, `seed` for demo data).
  These edges are the future talent graph in relational form
  (Student→HAS_SKILL→Skill, Student→HAS_INTEREST→Interest); evidence/import
  pipelines will only add new `source` values. Career/research interests stay
  free text — candidates for future nodes, not nodes yet.
- Photos without new infrastructure: students link an `avatar_url`; admins may
  set the university-controlled `photo_url`. Server-side uploads via presigned
  S3 URLs are the documented upgrade (still no S3 in the MVP).
- Directory (class detail/roster, structure tree) is same-university-verified
  only, paginated (`limit ≤ 100`). Structure admin is create + rename; no
  deletes in the MVP (cascades are destructive — explicit decision).
- Frontend: `/app/profile`, `/app/profile/edit`, `/app/people/[id]`,
  `/app/class`, `/app/admin`, plus an `/app` dashboard with academic
  breadcrumb. UI distinguishes verified (locked) cards from editable cards.

## 10. Forum foundation (implemented in 2B-A)
- **Model:** `forums` (`id`, `class_id`→`classes.id CASCADE`, `name`, `description`, `status` PENDING/APPROVED/REJECTED, `created_by`/`approved_by`→`users.id SET NULL`, `created_at/updated_at`, `uq_forums_class_name`, `ix_forums_*`) and `forum_memberships` (`forum_id`+`user_id` PK, `CASCADE` both). `ForumProposal` = `Forum` row with `PENDING`.
- **Lifecycle:** student (verified class member, STUDENT/CLASS_REP) proposes → `PENDING`; class rep (verified `CLASS_REP` of same `class_id`) approves/rejects → `APPROVED`/`REJECTED`. Rejected stays recorded, not active.
- **Authorization (server-side, reused RBAC):** propose/view-approved/join requires verified membership of that `class_id`; faculty/staff/admin without class membership blocked; rep can only manage own class; ID guessing blocked via class check; faculty/staff never auto-access student forums.
- **Membership:** `join`/`leave` + `list joined`, unique per pair, requires approved forum + class membership, 409 on duplicate.
- **API:** `GET /classes/{id}/forums`, `GET /classes/{id}/forums/proposals` (rep only), `POST /classes/{id}/forums`, `GET /forums/{id}`, `PATCH /forums/{id}/review`, `POST /forums/{id}/join`, `DELETE /forums/{id}/members/me` (+ `POST /leave`), `GET /forums/joined`.
- **Frontend:** class page shows class info, approved forum cards (member count, joined badge), propose form, rep proposal queue, Join/Leave; links to forum pages.
- **Seed:** 4 approved + 1 pending in CS-2024-A, 1 in CS-2024-B, memberships for ada/ben/rep.

## 11. Forum discussion (implemented in 2B-B)
- **Models:** `posts` (`id`, `forum_id`→`forums.id CASCADE`, `author_id`→`users.id SET NULL`, `content Text`, `created_at/updated_at`, `ix_posts_forum_id/author_id/created_at`); `comments` (`id`, `post_id`→`posts.id CASCADE`, `author_id SET NULL`, `content`, timestamps, `ix_comments_*`); `post_reactions` (`post_id`+`user_id` PK → `CASCADE`, single LIKE, `ix_*`); `notifications` (`id`, `user_id`→`CASCADE`, `actor_id SET NULL`, `type` COMMENT_ON_POST, `post_id/forum_id/comment_id SET NULL`, `message`, `is_read`, `created_at`, `ix_*`). Deleting forum cascades to posts→comments→reactions; deleting post/comment never deletes user/class/university.
- **Authorization:** only members of an `APPROVED` forum (or class rep of its class) may create/list posts/comments/likes; pending/rejected forums 404; cross-class/faculty 403; post delete: owner or rep of own class; comment delete: owner or rep of own class; rep cannot moderate other class. All via `get_current_user` + class-membership + forum-membership checks — no second auth system.
- **API:** `POST /forums/{fid}/posts`, `GET /forums/{fid}/posts?limit&offset` (newest first, `limit≤100`, `total/limit/offset`), `GET /forums/{fid}/posts/{pid}`, `DELETE /forums/{fid}/posts/{pid}`; `POST /forums/{fid}/posts/{pid}/comments`, `GET .../comments?limit&offset` (chronological), `DELETE .../comments/{cid}`; `POST .../like`, `DELETE .../like` (409 on duplicate, like_count returned); `GET /notifications`, `PATCH /notifications/{id}/read`. Counts (`like_count`,`comment_count`,`liked_by_me`,`is_own`,`author_display_name`) returned in post list to avoid N+1 — batched `GROUP BY` + `IN` queries for counts/likes/names, single page query + aggregates.
- **Pagination & performance:** posts `limit 20 default`, comments `50`, max 100; `newest first` via `created_at DESC, id DESC` (tie-breaker); comment `created_at ASC`; counts via `GROUP BY`; liked set via single `IN`; joins for author `Profile.display_name`; no per-post request.
- **Notifications (MVP, synchronous, no email/push/WS):** on `create_comment`, if `post.author_id != comment.author_id` inserts `notifications` (`COMMENT_ON_POST`) for post author; `GET /notifications` ordered `created_at DESC` paginated; `PATCH /notifications/{id}/read`.
- **Frontend:** `/app/class` links approved forums → `/app/forums/[forumId]` (forum header, member count, composer, post list with pagination, like button with count+state, expandable comment list + composer, delete own post/comment, rep sees delete). `/app/notifications` lists notifications, mark read. Reuses `inputClass/button*` primitives, visually consistent (not social-media clone, class/forum breadcrumb kept). Plain text composer, plain text comments, optimistic like only via refetch (safe).
- **Seed:** `General Discussion` 4 posts, `DSA Doubts` 4, `Project Discussion` 3, `Resources` 2; comments on "How do we approach graph traversal" and "Hey everyone", likes on first 2 posts per forum, notification for post author, idempotent via content equality + `IN` checks.
- **Extensibility:** `Post`/`Comment` content is plain Text, ready for future `mentions` (no autocomplete/search), attachments via S3 presigned URLs (no local uploads), mentions not implemented.

## 12. Connections (implemented in 3A)
- **Model:** `connections` (`id`, `requester_id`→`users.id CASCADE`, `recipient_id`→`users.id CASCADE`, `status` PENDING/ACCEPTED/REJECTED, `created_at/updated_at`, `ck_connections_no_self`, `uq_connections_pair` on (requester_id, recipient_id), `ix_connections_*`, `ix_connections_pair_status`). One row per student pair; unordered uniqueness enforced at service layer (check both directions before insert); cancellation/removal = DELETE, REJECTED persists (new request after REJECTED deletes old row). Deleting a user cascades only their connections, never university/class/identity data.
- **State machine:** NONE → PENDING (request) → ACCEPTED or REJECTED (recipient only) → DELETE (cancel by requester if PENDING, remove by either if ACCEPTED). Rejected can be re-requested (old REJECTED row deleted on new request). Duplicate/ reverse pending/ already-connected → 409.
- **Authorization (server-side):** only verified students (role STUDENT or CLASS_REP, status VERIFIED) can manage connections; `A != B`; B must exist and be verified student; A and B must share a verified university (same-university check); only recipient can accept/reject, only requester can cancel, either connected party can remove; cross-university → 403; unrelated user cannot accept/reject/cancel/remove → 404.
- **API:** `POST /connections/{user_id}/request` (201), `POST /connections/{user_id}/accept`, `POST /connections/{user_id}/reject`, `DELETE /connections/{user_id}/request` (cancel), `DELETE /connections/{user_id}` (remove), `GET /connections` (my accepted), `GET /connections/requests/incoming`, `GET /connections/requests/outgoing`, `GET /connections/{user_id}/status` (NONE/PENDING_OUTGOING/PENDING_INCOMING/CONNECTED/REJECTED), `GET /connections/{user_id}/mutuals` (count + users). All require `Authorization: Bearer`.
- **Connection status:** deterministic status derived from row direction + status; used on profile view (`/app/people/[id]`) to show Connect / Request Sent / Accept-Reject / Connected-Remove + mutual count. Directory (`/app/class` classmates) also shows per-member state via batch fetches of connections/incoming/outgoing (no per-member N+1).
- **Mutual connections:** efficient relational query: fetch connected ids for caller and target via two `SELECT ... WHERE status=ACCEPTED AND (requester=me OR recipient=me)` queries (single DB call each), intersect in Python, then one batched `IN` query for profile info of mutuals. No full university load, no N+1.
- **Notifications (MVP, synchronous):** on `send_request` inserts `notifications` for recipient (`CONNECTION_REQUEST` "A student sent you a connection request."); on `accept_request` inserts for requester (`CONNECTION_ACCEPTED` "Your connection request was accepted."). Reuses existing `notifications` table; `GET /notifications` already lists them.
- **Frontend:** `/app/connections` page with My Connections / Incoming / Sent sections; `/app/people/[id]` shows connection action + mutual count; `/app/class` classmates list shows Connect / Request Sent / Accept-Reject / Connected per member; NavBar + dashboard add Connections link. Uses `buttonPrimaryClass/buttonSecondaryClass` primitives, loading/disabled/error states.
- **Seed:** `ada→ben ACCEPTED`, `ada→cara ACCEPTED`, `ben→diana ACCEPTED`, `cara→diana PENDING` plus notifications for pending; demonstrates connected, pending outgoing/incoming, none, mutual (ada-diana mutual = ben). Idempotent via either-direction existence check.
- **Graph compatibility:** `Connection` with `status=ACCEPTED` is the `CONNECTED_TO` edge for Phase 3B graph projection: `Student A —CONNECTED_TO→ Student B` via `SELECT requester_id, recipient_id FROM connections WHERE status='ACCEPTED'` (undirected edge, query both directions).

## 13. University Network Graph Data Layer (implemented in 3B-A)
- **Architecture:**
  ```
  PostgreSQL
      ↓
  Graph Service (app/modules/graph/service.py)
      ↓
  Graph API (GET /api/v1/graph/me)
      ↓
  Graph Visualization (Phase 3B-B)
  ```
  PostgreSQL remains source of truth; graph is ephemeral, derived per request, no persistence, no Neptune/Redis/Kafka.

- **Source tables:** `users + profiles + university_identities + universities/departments/programs/batches/classes + forum_memberships/forums + profile_skills/skills + profile_interests/interests + connections`.

- **Node types (`GraphNodeType`):** `STUDENT, UNIVERSITY, DEPARTMENT, PROGRAM, BATCH, CLASS, FORUM, SKILL, INTEREST`.

- **Edge types (`GraphEdgeType`):** `BELONGS_TO (dept→uni), ENROLLED_IN (student→uni), IN_PROGRAM (program→dept), IN_BATCH (batch→program), IN_CLASS (class→batch + student→class), PARTICIPATES_IN (student→forum), HAS_SKILL, HAS_INTEREST, CONNECTED_TO (student→student)`. `MEMBER_OF` reserved but not used in MVP.

- **Boundary:** Root is authenticated verified student (role STUDENT/CLASS_REP, status VERIFIED). Immediate one-hop network only: university hierarchy for that student, joined `APPROVED` forums, declared skills/interests, accepted connections' public profiles. No recursive expansion (`A→B→C` does not expose `C` in `A`'s graph).

- **Privacy:** Student nodes expose only public fields (`display_name`, `headline`, `avatar_url`, `role`) — same as `PublicProfile`; never `email`, `student_no`, `password`, `session`, `enrollment_code`. Structure/skill/interest/forum nodes expose only `label` + non-sensitive metadata (`code`, `degree_level`, `description`). Cross-university filtering: connections filtered to same `university_id`; other university's university/skill/forum nodes never included.

- **Authorization:** `GET /graph/me` requires `Authorization: Bearer`; unauthenticated →401, unverified/non-student →403 (via `_require_verified_student`). Pending/rejected connections and unjoined/pending/rejected forums never become edges — only `status=ACCEPTED` and `status=APPROVED + membership`.

- **Service correctness:** Builds `nodes` dict + `edges` dict deduplicated by `id`, deterministic sorted output, validates every edge's `source`/`target` in `node_ids`, uses batched queries (`JOIN` + `IN`) to avoid N+1, no full university load. All IDs are string UUIDs, edge IDs deterministic (`{source}-{target}-{type}`).

- **API:** `GET /api/v1/graph/me` → `GraphResponse {root_id, nodes:[GraphNode], edges:[GraphEdge]}`.

- **Frontend consumption (3B-B):** Typed client calls `GET /graph/me` and renders with React Flow (`reactflow@11`, client component, fitView, no SSR graph sync).

- **Future Phase 4:** Talent edges (skill/interest) already present; Phase 4 can add `RECOMMENDED_FOR`, `SIMILAR_TO` without schema change by enriching `metadata` or adding similarity views — still derived from same relational tables.

- **Why no graph DB:** MVP ego-graphs are bounded depth 1, SQL joins + batched `IN` are <10ms on Free Tier RDS; dedicated graph store would add cost/ops with no MVP benefit. Documented scale path: materialized views → background recompute → only then graph store if proven.

## 14. University Network Graph Visualization (implemented in 3B-B)
- **Route:** `/app/network` — page title *Your University Network* + subtitle *Your academic context, communities, interests, skills, and connections in one network.* Added to NavBar and Dashboard (`/app`). Protected via `RequireAuth` (UX gate) + server-side `GET /graph/me` auth.
- **Library:** `reactflow@11` (single graph library, chosen for React-native integration, TypeScript, `Controls`/`MiniMap`/`Background` out-of-box, clean Next.js client-component usage, no heavy D3/Cytoscape imperative layer). Isolated to `components/network/NetworkGraph.tsx`.
- **Data flow:** `fetchGraph(token)` → `GraphResponse` (real DB data, no mocks) → `layoutNodes()` → `ReactFlow` nodes/edges. One fetch on mount, no per-node fetching, no caching infra.
- **Node visuals:** Distinct `typeStyles` (STUDENT blue, UNIVERSITY amber, DEPARTMENT orange, PROGRAM purple, BATCH teal, CLASS emerald, FORUM pink, SKILL zinc-900 white, INTEREST sky) with icon + label, `CLASS`/`FORUM`/`SKILL`/`INTEREST` pills, STUDENT nodes `👤` + display_name. Root (`graph.root_id`) larger (180px vs 150px), dark border `#18181b`, shadow, `STUDENT · You` badge.
- **Edge visuals:** `CONNECTED_TO` animated blue, others `#a1a1aa`; labels (`connected`/`skill`/`interest`/`forum`/`class`/`university`) for root-origin edges, hierarchy edges unlabeled to avoid clutter. All edges `Bezier`.
- **Layout:** Deterministic hierarchical-radial around root: chain `UNIVERSITY(-400)`→`DEPARTMENT(-300)`→`PROGRAM(-200)`→`BATCH(-100)`→`CLASS(50)`→`ROOT(170)` vertical spine; `FORUM` left (`x=-320`), `SKILL` right-upper (`x=320`), `INTEREST` right-lower, `CONNECTED` students south (`y=360`, spread `x`). Handles 0-n per type, fallback random, auto `fitView({padding:0.2})` on mount and via Fit/Recenter.
- **Interaction:** Pan & zoom (mouse wheel + drag), zoom in/out, fit, recenter via header buttons + `Controls`; `MiniMap` + `Background`; node click → `NodeDetails` panel (bottom-right), hover shows cursor; pane click clears selection.
- **Node details:** Lightweight panel: STUDENT (name, headline, role, *View profile →* link to `/app/people/[id]` for non-root), CLASS (code), FORUM (description, class_id), SKILL (skill), INTEREST (kind), UNIVERSITY/DEPARTMENT/PROGRAM/BATCH (code/degree/year). No private fields (`email`, `student_no` never exposed). Reuses `Link` navigation, `button` close.
- **Controls:** Zoom +, Zoom −, Fit, Recenter only (via `useReactFlow`). No 17-knob panel.
- **Loading / error / empty:** `Loading` while fetching; error → *Unable to load your network. [Retry]*; empty (≤2 nodes) → *Your network is still growing…* with hint + node counts, else render graph.
- **Responsive:** `h-[620px] lg:h-[700px]` flex container, `relative flex-1` ReactFlow, Tailwind responsive, desktop-first, tablet works, no mobile-specific graph.
- **Architecture isolation:** `frontend/components/network/NetworkGraph.tsx` holds all `reactflow` imports/styles/layout, `NodeDetails` inside same file (small), page `app/app/network/page.tsx` handles fetch/state/error/empty and composes `NetworkGraph`. No second frontend graph model — uses `GraphNode/GraphEdge/GraphResponse` from `lib/api.ts`.
- **Final chain:**
  ```
  PostgreSQL
    ↓
  Graph Service
    ↓
  Graph API (GET /api/v1/graph/me)
    ↓
  NetworkGraph component (reactflow)
    ↓
  Interactive University Network
  ```
