# Tomorrow Agent Hub — Build Roadmap

Spec: `docs/superpowers/specs/2026-08-04-tomorrow-agent-hub-design.md`
Source of truth for screens/behavior: `docs/Tomorrow Agent Hub - Scope Appendix.xlsx`

The full build is executed as eight stage plans, in order. Each stage plan is written
just-in-time at its boundary (so it reflects what earlier stages actually produced) and ends
with working software, green local CI, and a git commit trail. Detailed plans live beside this
file as `2026-08-04-stage-<letter>-<name>.md`.

| Stage | Plan | Delivers | Done when |
|---|---|---|---|
| A | stage-a-foundations | Python 3.12 venv (uv), embedded Postgres 16 + pgvector, API core (config/db/health), Alembic + migration 1 (users, municipalities, departments, user_departments, invitations, password_reset_tokens, audit_log), pytest harness on embedded PG, vitest harness, CI workflow, secrets | `pytest` green incl. DB round-trip; `tsc`/eslint/vitest green; migration up/down clean |
| B | stage-b-auth | Auth APIs (login/forgot/reset/accept-invite/change-password, JWT + token_version, rate limits), invitations API, NextAuth wiring, /login /accept-invite /forgot /reset pages, app shell + sidebar + next-intl (he/en, RTL), /profile, role redirects | All auth flows work in browser via local outbox emails; token-lifecycle + rate-limit tests green |
| C | stage-c-admin | /system/municipalities, /system/users, /system/categories, /admin/users, /admin/departments (archive/restore/purge fields), scope-enforced CRUD APIs, audit logging, first access-control matrix tests | Both admin areas fully operable; matrix tests for these resources green |
| D | stage-d-content | Storage provider (R2 ⇄ local disk + signed URLs), kb_documents + upload/replace/delete, ingestion pipeline (extract → chunk 800/150 → embed → chunks table, HNSW), SKIP LOCKED worker, indexing status UI, /knowledge pages | Upload → worker indexes → chunks queryable; delete cascades chunks in-transaction; extraction for PDF/DOCX/PPTX/XLSX |
| E | stage-e-boards | Boards API + full-text search (he+en tsvector), /board, /municipality, item detail, publish dialog, comments/likes, department areas (/departments/[id] files + posts), 404 cross-scope rule | Board + department flows work; their matrix tests green; board/department content flows into ingestion |
| F | stage-f-chat | LLM provider (OpenAI ⇄ fakes), permission-filtered retrieval SQL (top 12, ≥0.35), SSE streaming chat, citations, conversations CRUD, unanswered logging, 60 msg/h limit, /chat UI | Chat answers with citations from seeded docs via fakes; cross-department leak question returns not-covered; RAG eval (30 q) green |
| G | stage-g-metrics | daily_metrics rollup, cron endpoints (digest Mon 08:00 Asia/Jerusalem, rollup, purge) with CRON_SECRET + idempotency + run records, weekly digest email, /admin/stats, /system/stats with CSV export | Dashboards render from rollups; crons idempotent; digest lands in local outbox |
| H | stage-h-polish | i18n/RTL sweep of every screen, seed/demo data (2 municipalities, roles, sample docs), full access-control matrix, load-relevant indexes, README/runbook updates, final full-CI verification | Definition of done in the spec fully met |

Standing risks and fallbacks (checked at the stage that hits them):
- Embedded PG package lacks Windows wheels → portable PostgreSQL zip + prebuilt pgvector DLL (Stage A, explicit fallback steps in plan).
- `unstructured` install fails on Windows/Py3.12 → per-format extractors via pypdf / python-docx / python-pptx / openpyxl behind the same `extract()` interface (Stage D).
