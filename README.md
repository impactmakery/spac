# Tomorrow Agent Hub

Shared knowledge and AI assistant platform for municipalities: global knowledge base,
shared boards (global + per municipality), private department areas, and a chat assistant
grounded in platform documents with permission-aware retrieval (RAG).

Requirements live in `docs/` (PRD + per-screen scope appendix). Project context for AI-assisted
development is in `CLAUDE.md`.

## Layout

- `web/` — Next.js 15 frontend (scaffold with create-next-app, see below)
- `api/` — FastAPI backend + ingestion worker + cron jobs
- `docs/` — PRD and scope appendix
- `docker-compose.yml` — local PostgreSQL 16 with pgvector

## Local setup

1. `cp .env.example .env` and fill the values.
2. `docker-compose up -d` (Postgres 16 + pgvector on :5432).
3. Backend: `cd api && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt && uvicorn app.main:app --reload` (http://localhost:8000/health).
4. Frontend: `cd web` — first time: `npx create-next-app@latest . --typescript --tailwind --eslint --app`; then `npm run dev` (http://localhost:3000).

## Deploy targets

Vercel (web) + Railway (api, worker, cron) + Cloudflare R2 (files) + Resend (email) + Sentry.
