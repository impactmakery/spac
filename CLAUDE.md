# Tomorrow Agent Hub

Shared knowledge + AI assistant platform for multiple municipalities. Custom build (not Base44).
Full requirements: `docs/Tomorrow Agent Hub - PRD v0.5.docx`. Per-screen scope with every route,
rule, and acceptance item: `docs/Tomorrow Agent Hub - Scope Appendix.xlsx`. Treat the scope
appendix as the source of truth for screens and behavior.

## What this is

- Municipalities > departments > users. Three roles: system admin, municipality admin, department user.
- One global knowledge base (all users). Global shared board (all users). One board per municipality
  (members only). One content area per department (members + their admins only).
- Chat assistant (RAG) grounded ONLY in platform documents, with the permission filter inside the
  retrieval SQL — a user must never get an answer sourced from content they cannot see.
- Usage dashboards, tiered: system admin sees everything; municipality admin sees own municipality.
- Bilingual Hebrew/English, full RTL. Assistant answers in the language of the question.

## Stack (decided — do not substitute without asking)

- `web/` Next.js 15 (App Router) + TypeScript + Tailwind + next-intl. Auth via NextAuth
  credentials provider delegating to the API. Deploys to Vercel.
- `api/` Python 3.12 + FastAPI + SQLAlchemy + Alembic. LangChain for RAG orchestration.
  Deploys to Railway (web service + ingestion worker + cron service).
- PostgreSQL 16 + pgvector (single DB: app data AND embeddings; HNSW index). Local dev via
  `docker-compose up` (root compose file).
- Cloudflare R2 for files (server-side upload, presigned downloads, 25 MB cap,
  PDF/DOCX/PPTX/XLSX only).
- OpenAI: chat model from `LLM_MODEL` env (launch: gpt-4.1), embeddings from `EMBEDDING_MODEL`
  (launch: text-embedding-3-large). Resend for email. Sentry for errors.

## RAG spec (hard requirements)

1. Ingestion: extract (unstructured lib) -> chunk 800 tokens / 150 overlap -> embed -> insert into
   `chunks` with source_type, source_id, municipality_id, department_id, visibility
   (global | municipality | department). Job queue = Postgres table with SKIP LOCKED; 3 retries.
2. Retrieval: top 12 by cosine, drop below 0.35 similarity, and the WHERE clause enforces:
   visibility='global' OR municipality_id = :user_muni OR department_id IN (:user_depts).
   Never filter after retrieval — filter IN the query.
3. Generation: answer only from retrieved chunks; stream via SSE; numbered citations linking to
   source; empty retrieval => standard "not covered" reply + row in unanswered_questions.
4. Deleting a file/document deletes its chunks in the same transaction.

## Conventions

- All schema changes through Alembic migrations. No manual DDL.
- Every user-facing string in `web/messages/he.json` + `en.json` — no hardcoded literals.
- Server-side permission check on every API route; UI state is never the enforcement point.
- Cross-scope reads return 404 (not 403) so existence isn't leaked.
- Admin mutations write to the append-only `audit_log` table.
- CI (GitHub Actions): web = tsc --noEmit, eslint, vitest; api = ruff, mypy, pytest.
  The access-control pytest suite (permission matrix) must pass on every PR.

## Build order

1. Scaffold: `npx create-next-app@latest web` (TS, Tailwind, App Router, ESLint); api deps from
   `api/requirements.txt`; `docker-compose up -d`; first Alembic migration (users, municipalities,
   departments, user_departments, invitations, sessions/token_version).
2. Auth + invitations (login, accept-invite, forgot/reset, role-based redirect).
3. Municipalities/departments/users admin screens (/system/*, /admin/*).
4. Knowledge base + file pipeline (R2 upload, ingestion worker, chunks table).
5. Boards (global + municipality) + department areas + comments/likes.
6. Chat (conversations, SSE streaming, citations, unanswered logging).
7. Usage rollups + dashboards. 8. Digest + crons. 9. i18n/RTL polish. 10. Test suites from the
   "Quality, Security & Handover" rows of the scope appendix.
