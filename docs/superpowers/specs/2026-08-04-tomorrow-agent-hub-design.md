# Tomorrow Agent Hub — Build Design

Date: 2026-08-04
Status: Approved by user (full build, no pauses)

## Sources of truth

- `docs/Tomorrow Agent Hub - PRD v0.5.docx` — product requirements.
- `docs/Tomorrow Agent Hub - Scope Appendix.xlsx` — per-screen scope; authoritative for every
  route, rule, and acceptance item (per `CLAUDE.md`).
- `CLAUDE.md` — decided stack and build order.

This design does not restate those documents. It records the decisions they leave open and the
local-environment adaptations agreed with the user. Where this file and the scope appendix
conflict, the appendix wins.

## Scope of this build

Full platform, built sequentially per the CLAUDE.md build order (scaffold → auth/invitations →
admin screens → knowledge base + ingestion → boards + department areas → chat/RAG → dashboards →
digest/crons → i18n/RTL polish → test suites).

**Definition of done:** web + API + ingestion worker + local DB all run locally; demo seed data
(2 municipalities, departments, users in all three roles, sample documents); every appendix
screen functional in Hebrew and English with correct RTL; local CI green — `tsc --noEmit`,
eslint, vitest, ruff, mypy, pytest — including the access-control permission matrix suite and
the 30-question RAG grounding eval with its cross-department leak check.

**Out of scope:** cloud deployment (Vercel, Railway, R2, Resend, Sentry accounts), GitHub repo
creation / branch protection / DNS, UAT. The CI workflow file, Dockerfile, and Sentry wiring
ship in the repo ready for those, inert until credentials/remotes exist.

## Local environment adaptations (dev-only; production paths unchanged)

1. **Python 3.12 via `uv`** — `api/.venv` runs CPython 3.12 (spec-pinned) managed by uv;
   system Python 3.14 untouched.
2. **Embedded PostgreSQL 16 + pgvector** — no Docker on this machine. Primary: pip-managed
   embedded Postgres bundling pgvector. Fallback: portable official PostgreSQL zip + prebuilt
   pgvector DLL. A dev script starts/stops it; pytest fixtures provision throwaway databases on
   it. `docker-compose.yml` remains for CI/production parity.
3. **Provider interfaces with local fallbacks**, selected at startup: real client when the env
   key is set, local fallback when empty. No code change to switch — only `.env`.
   - Storage: Cloudflare R2 (boto3, presigned URLs) ⇄ local-disk store under `api/var/files`
     with HMAC-signed, expiring download URLs served by the API.
   - Email: Resend ⇄ local outbox directory (`api/var/outbox`, one JSON per message) so invite
     and reset links are retrievable and the flows fully testable.
   - LLM/embeddings: OpenAI (`LLM_MODEL`, `EMBEDDING_MODEL`, embeddings truncated to 1536 dims)
     ⇄ deterministic hash-based fake embeddings + a fake chat model that composes answers from
     the retrieved chunks. Chat, SSE streaming, citations, unanswered logging, and the RAG eval
     all run end-to-end on the fakes. Tests always use the fakes.
4. **Secrets** — generate real random values for `JWT_SECRET`, `NEXTAUTH_SECRET`, `CRON_SECRET`
   in `.env`.
5. **Git** — `git init` now; commit at each stage boundary. No remote until the user creates one.

## Architecture decisions

### API (`api/`)

- Layout: `app/core` (config via pydantic-settings, security, deps), `app/models` (SQLAlchemy 2
  declarative), `app/schemas` (Pydantic), `app/routers` (one module per appendix API row),
  `app/services` (permissions, audit, storage, email, invitations), `app/rag` (extraction,
  chunking 800/150, retrieval, generation, SSE), `app/worker.py` (ingestion queue consumer,
  Postgres SKIP LOCKED, 3 retries with backoff), `app/crons` (digest, rollup, purge — HTTP
  endpoints guarded by `CRON_SECRET`, idempotent per period, run records logged).
- Auth: bcrypt password hashes; JWT (HS256, `JWT_SECRET`) carrying user id, role,
  municipality_id, department ids, and `token_version`; re-verified against the DB on every
  request (token_version mismatch = 401, satisfies the 60-second deactivation rule). Single-use
  hashed tokens for invitations (7-day) and password reset (1-hour). Rate limits 10/15 min/IP
  on login and forgot. Chat limited to 60 messages/hour/user.
- Full schema (grown via Alembic migrations per stage): municipalities, departments, users,
  user_departments, invitations, password_reset_tokens, categories (bilingual names),
  kb_documents, board_items, board_comments, board_likes, department_files, department_posts,
  department_post_comments, chunks (`vector(1536)`, HNSW cosine index, source_type, source_id,
  municipality_id, department_id, visibility), conversations, messages, unanswered_questions,
  ingestion_jobs, daily_metrics, cron_runs, audit_log (append-only).
- Hard rules kept exactly as documented: permission filter inside the retrieval SQL (top 12
  cosine, drop < 0.35); cross-scope reads return 404 (the appendix's lone 403 mention for
  department areas is resolved in favor of the CLAUDE.md-global 404 rule); file deletion removes
  chunks in the same transaction; admin mutations audit-logged; Alembic-only DDL.

### Web (`web/`)

- App Router with `app/[locale]/` (next-intl; `he` default, `dir=rtl` on html for Hebrew).
  Route groups: `(auth)` — login, accept-invite, forgot/reset; `(app)` — chat, knowledge,
  board, municipality, departments/[deptId], profile, with the role-aware sidebar shell;
  `admin/*` and `system/*` per the appendix.
- NextAuth credentials provider delegates to `POST /api/auth/login`; the API JWT is stored in
  the NextAuth JWT session and sent as a Bearer token. Server components/route handlers proxy
  the API; the chat page streams SSE from the API directly with the token.
- Every user-facing string in `web/messages/he.json` + `en.json`.

### Testing

- pytest: access-control matrix (each role × each cross-scope resource → 403/404), RAG
  grounding eval (20 answerable must cite correct source, 10 unanswerable must return
  not-covered, incl. cross-department leak), unit tests for chunking, retrieval SQL, token
  lifecycle, cron idempotency. Runs on embedded Postgres with fake providers.
- vitest: web utilities and key components. `tsc --noEmit` + eslint + ruff + mypy all green.
- GitHub Actions workflow authored per the appendix (web job + api job), effective once pushed.
