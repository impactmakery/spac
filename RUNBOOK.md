# Runbook

Operational procedures. For *why* the system is shaped this way see `ARCHITECTURE.md`.

## Services

| Service | Platform | Command |
|---|---|---|
| Web | Vercel | Next.js build (automatic on push to `main`) |
| API | Railway | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Ingestion worker | Railway | `python -m app.worker` |
| Cron | Railway | HTTP calls to the cron endpoints below |
| Database | Railway PostgreSQL (pgvector) | — |
| Files | Cloudflare R2 | — |

Both Railway services run in region `ams` (Amsterdam) — the users are in Israel, and
`sfo` added roughly 250–300 ms to every request.

## Deploying

Push to `main`. Vercel builds the web app; Railway rebuilds the API and worker.

**Migrations run automatically.** The API container's start command is
`alembic upgrade head && uvicorn …`, so the schema is upgraded before the new code
serves its first request and a deploy never serves an out-of-date schema. Alembic is
idempotent, so a restart or a second instance is harmless.

To run one by hand anyway (a failed boot, or a migration you want to apply ahead of a
deploy):

```
railway run --service api alembic upgrade head
```

Every migration must still be additive-then-backfill if it touches a column already in
use: the worker and any still-draining API instance run the old code for a few seconds
during a rollout.

## Scheduled jobs

All cron endpoints require the `CRON_SECRET` bearer token and are idempotent per period,
so a retry or a double-fire is harmless.

| Endpoint | Schedule | Does |
|---|---|---|
| `POST /api/cron/metrics-rollup` | nightly 02:00 | rolls usage into `daily_metrics` |
| `POST /api/cron/archive-purge` | nightly 03:00 | deletes archived departments past their retention, and sweeps chat history, retrieval debug rows and recorded errors past 90 days |
| `POST /api/cron/weekly-digest` | Mondays 08:00 Asia/Jerusalem | emails the digest to opted-in users |

Each run records a row in `cron_runs`. If a dashboard looks stale, check there first —
a missing row means the scheduler never fired, a present row with an error means the job
did. Failed runs also appear on `/system/errors`.

The dashboard reads the stored rollups, not live counts, so changing what a metric means
only affects days rolled up afterwards. To make a whole series mean one thing:

```bash
railway run --service api python scripts/rebuild_rollups.py 90
```

`rollup_day` deletes and rebuilds the day it is given, so running this twice is the same
as running it once.

## Common situations

### Start at /system/errors

A system admin's **תקלות / Errors** page lists everything the platform could not do:
unhandled server errors with their tracebacks, documents that would not index, and cron
runs that failed. Container logs on Railway last seven days; these rows last 90, so a
report about last week is answerable from the page rather than from memory.

Every failed document has a **Try again** button, which puts it back in the ingestion
queue — the first thing to reach for, since most indexing failures are transient.

### A document is stuck on "pending"

The worker is not running or not reaching the database. Check the worker logs on Railway.
The queue is a table, so you can see the backlog directly:

```sql
SELECT status, count(*) FROM ingestion_jobs GROUP BY status;
SELECT id, source_type, attempts, last_error FROM ingestion_jobs
 WHERE status IN ('queued','failed') ORDER BY id DESC LIMIT 20;
```

Restarting the worker is safe at any time — an interrupted job is reclaimed by the next
poll, because the claim is transactional.

### A document is marked "not indexable"

Three attempts failed; `ingestion_jobs.last_error` says why. Usually a scanned PDF with
no text layer (there is no OCR), or a corrupt upload. Re-index from the document's admin
screen after fixing the file.

### The assistant answers "not covered" for something that is in a document

In order of likelihood:

1. The document is not indexed yet — check its status.
2. The asking user genuinely cannot see it. Confirm the visibility and the user's
   department membership. This is correct behaviour, not a bug.
3. `EMBEDDING_MODEL` was changed without re-embedding, so old and new vectors are not
   comparable. Fix with `python scripts/reembed.py --run`.

### The assistant answers in the wrong language

The system prompt pins the answer to the language of the *question*, not the sources. If
this regresses, it is `SYSTEM_PROMPT` in `api/app/rag/generation.py`, and there is a test.

### Generation fails or returns nothing

The model chain (`LLM_MODEL` then `LLM_FALLBACK_MODELS`) is walked in order on error or
empty content. If every model fails the request errors — check the API logs for which
provider rejected it. Free-tier models rate-limit aggressively; that is what the fallback
chain is for. A failure *after* streaming has begun cannot be retried and surfaces to the
user.

## Rotating credentials

Every key lives in the platform's environment settings, not in the repository.

| Key | Where | Notes |
|---|---|---|
| `JWT_SECRET` | Railway (api) | rotating **logs every user out** |
| `AUTH_SECRET` / `NEXTAUTH_SECRET` | Vercel | same effect |
| `LLM_API_KEY`, `EMBEDDING_API_KEY`, `OPENAI_API_KEY` | Railway | no user impact |
| `R2_*` | Railway | no user impact; downloads use presigned URLs |
| `CRON_SECRET` | Railway + scheduler | update both together or crons start 401ing |
| `RESEND_API_KEY` | Railway | no user impact |

The API refuses to boot without `JWT_SECRET`, deliberately — an empty signing key is
worse than a failed deploy.

## Backups

**Backups are not currently enabled.** They are not gated by plan — Railway schedules
them per volume, in the database service's **Backups** tab. Nothing needs buying to turn
them on; it just has not been done yet.

Railway's retention is fixed per schedule, and multiple schedules can run on one volume:

| Schedule | Retention |
|---|---|
| Daily | 6 days |
| Weekly | 1 month |
| Monthly | 3 months |

The agreed scope asks for "nightly automated backups with 30-day retention". No single
Railway schedule provides that — daily keeps only 6 days. Enabling **all three** together
gives 6 days at nightly granularity plus a month of weeklies and a quarter of monthlies,
which is longer-reaching than the spec but coarser between days 7 and 30. If a true
30-day nightly history is required, it needs `pg_dump` on a schedule into R2, which is
not built.

Restores are non-destructive: Railway mounts the backup as a **new** volume and unmounts
the old one rather than overwriting it, so the restore rehearsal the scope asks for can
be done safely.

Manual backups are capped at 50% of the volume's size.

R2 holds the original uploaded files, so file content survives a database loss — but the
metadata, permissions, boards, conversations and audit log do not.

R2 holds the original uploaded files, so file content survives a database loss — but the
metadata, permissions, boards, conversations and audit log do not.

Manual dump:

```
railway run --service api pg_dump "$DATABASE_URL" -Fc -f backup.dump
```

## Verifying a deployment

Fastest end-to-end check that exercises every moving part:

1. Log in.
2. Upload a document to the knowledge base — proves R2 write + the API.
3. Wait for it to reach "indexed" — proves the worker and the embedding provider.
4. Ask the assistant a question it answers — proves retrieval and generation.
5. Confirm the answer carries a citation that opens the source — proves presigned reads.

If step 3 stalls, it is the worker or the embedding key. If step 4 returns "not covered"
with the document indexed, it is retrieval, not generation.

## Seeding a demonstration environment

```
cd api && python scripts/seed_demo.py --index
```

Two municipalities with Hebrew content pushed through the real pipeline. Idempotent, and
it refuses to run if the demo municipalities already exist. All demo accounts share the
password printed at the end. **Do not run this against an environment holding real
data** — it is safe by that check alone, not by design.

## Local development against production data

Don't. The test suite blanks provider credentials found in `.env` for exactly this
reason, but nothing stops a script. If you must inspect production, use a read-only
connection and never point the test suite at it — the suite writes to R2 and the database.
