# Tomorrow Agent Hub

Shared knowledge and AI assistant platform for municipalities: a global knowledge base,
shared boards (global + per municipality), private department areas, and a chat assistant
grounded in platform documents with permission-aware retrieval (RAG).

Bilingual Hebrew/English with full RTL support.

## Layout

- `web/` — Next.js 16 (App Router, TypeScript, Tailwind, next-intl) frontend
- `api/` — FastAPI backend, ingestion worker, and cron jobs
- `docker-compose.yml` — local PostgreSQL 16 with pgvector

Requirements documents are held outside this repository.

## Architecture

| Layer | Choice |
|---|---|
| Frontend | Next.js on Vercel; NextAuth credentials delegating to the API |
| Backend | FastAPI on Railway (web service, ingestion worker, cron service) |
| Database | PostgreSQL 16 + pgvector — application data and embeddings in one database |
| Files | Cloudflare R2, server-side upload, presigned downloads (25 MB cap) |
| AI | Any OpenAI-compatible provider (OpenAI, OpenRouter, …), pinned by env var |
| Email | Resend |

The assistant's permission filter runs **inside the retrieval SQL**, never as a
post-filter: a user can never receive an answer sourced from content they cannot see.

### AI providers

Generation and embeddings are configured independently, so they can live on
different providers — for example chat on OpenRouter's free models while
embeddings stay on OpenAI:

```
LLM_API_KEY=...            LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=google/gemma-4-26b-a4b-it:free
LLM_FALLBACK_MODELS=nvidia/nemotron-3-super-120b-a12b:free   # used when rate-limited
EMBEDDING_API_KEY=...      EMBEDDING_MODEL=text-embedding-3-large
```

Each API key travels with its own base URL, so one provider's key is never sent
to another's endpoint. Moving everything to OpenAI is just `OPENAI_API_KEY` plus
an OpenAI `LLM_MODEL`, with no other changes.

**Changing `EMBEDDING_MODEL` requires re-embedding** — vectors from different
models are not comparable:

```
python scripts/reembed.py --run
```

With no keys set the app still runs end to end on deterministic offline
providers. The test suite always uses those: keys in `.env` are ignored during
tests so the suite stays fast, free, and hermetic. Export a key in the shell to
opt in to the live RAG evaluation.

## Local setup

1. `cp .env.example .env` and fill in the values. Without API keys the app still runs
   end-to-end: file storage falls back to local disk, email to a JSON outbox
   (`api/var/outbox`), and embeddings/generation to deterministic offline providers.
2. Database — either:
   - `docker-compose up -d` (PostgreSQL 16 + pgvector on :5432), or
   - `cd api && python scripts/dev_db.py` for an embedded server needing no Docker.
3. Backend:
   ```
   cd api
   python -m venv .venv && .venv/Scripts/activate
   pip install -r requirements.txt
   alembic upgrade head
   python scripts/seed.py                 # first system admin
   uvicorn app.main:app --reload --port 8001
   ```
4. Ingestion worker (separate terminal): `cd api && python -m app.worker`
5. Frontend: `cd web && npm install && npx next dev -p 3001` → http://localhost:3001

## Tests

```
cd api && ruff check . && mypy app && pytest      # includes the access-control
                                                 # matrix and RAG grounding eval
cd web && npx tsc --noEmit && npm run lint && npm test
```

The access-control matrix (role × resource → 403/404) and the cross-department leak
test must pass on every pull request — a permission regression cannot merge.

The RAG grounding eval runs a reduced offline subset by default; set `OPENAI_API_KEY`
to run the full natural-language question set.

## Scheduled jobs

Cron endpoints require the `CRON_SECRET` bearer token and are idempotent per period:

| Endpoint | Schedule |
|---|---|
| `POST /api/cron/metrics-rollup` | nightly 02:00 |
| `POST /api/cron/archive-purge` | nightly 03:00 |
| `POST /api/cron/weekly-digest` | Mondays 08:00 Asia/Jerusalem |

## Deploy targets

Vercel (web) · Railway (api, worker, cron) · Cloudflare R2 (files) · Resend (email) · Sentry.
