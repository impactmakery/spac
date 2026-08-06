# Architecture

Companion to the README, which covers layout and local setup. This document explains
*why* the system is shaped the way it is, so the next person can change it safely.

## The one rule everything else serves

A user must never receive an answer sourced from content they cannot see.

Every other decision below follows from that. It is enforced in exactly one place — the
`WHERE` clause of the retrieval SQL — and asserted by a test suite that must pass on
every pull request. The UI hides things too, but UI state is never the enforcement point.

## Scopes and roles

```
Municipality ──< Department ──< (users, via user_departments)
```

| Role | Sees |
|---|---|
| `system_admin` | everything, across all municipalities |
| `municipality_admin` | own municipality: its departments, users, board, content |
| `department_user` | own municipality's board + the departments they belong to |

Content lives at one of three visibilities, which is what the retrieval filter keys on:

| Visibility | Who can read it | Source |
|---|---|---|
| `global` | every active user | knowledge base, global board |
| `municipality` | members of that municipality | municipality board |
| `department` | members of that department | department files and posts |

Cross-scope reads return **404, not 403** — a 403 confirms the resource exists, which
leaks the existence of another municipality's records.

### Browsing access and retrieval access are not the same thing

A municipality admin can open and read any department area in their municipality, but
**the assistant will not use that department's content as a source for them** unless they
are a member of the department. The scope appendix is explicit: department content is
"retrievable by the assistant for members only."

This looks like a bug from the outside and is not one. Do not "fix" it by widening the
retrieval predicate to include a municipality admin's departments — there is a test
(`test_municipality_admin_does_not_retrieve_non_member_department_content`) that pins the
rule precisely because the fix is tempting.

## Request path

```
Browser ──> Next.js (Vercel) ──> FastAPI (Railway) ──> PostgreSQL + pgvector
                 │                      │
            NextAuth session       Cloudflare R2 (files)
```

NextAuth holds the session cookie; the API is the only thing that reads the database.
The web app never talks to Postgres or R2 directly, so there is one place to audit for
permission checks. Every API route re-derives the caller's scope from the token rather
than trusting anything the client sends.

## The RAG pipeline

### Ingestion

```
upload ──> R2 ──> ingestion_jobs row ──> worker ──> chunks (content + embedding + tsvector)
```

The job queue is a Postgres table claimed with `FOR UPDATE SKIP LOCKED` — no broker to
run or pay for, and the queue is transactional with the data it describes. Three attempts
with exponential backoff, then the source is marked `not_indexable` with the error kept
for the admin screen.

Two details that are easy to get wrong and are deliberate:

- The claim uses `clock_timestamp()`, not `now()`. `now()` is the transaction start time,
  so a long-lived worker session would never see jobs enqueued after it began.
- Deleting a document deletes its chunks **in the same transaction**. A half-deleted
  document is a document whose content is still answerable.

### Chunking

800 tokens with 150 overlap, cut at paragraph boundaries rather than mid-sentence — a
chunk ending half-way through a clause embeds poorly and reads badly when cited. A single
block larger than the budget (a long table, an unbroken wall of text) falls back to token
windows. The document title is prepended to every chunk, so a passage retrieved from the
middle of a file still says what it came from.

### Retrieval — hybrid, permission-filtered

Two independent searches over the same rows, fused with Reciprocal Rank Fusion:

| Arm | Finds | Misses |
|---|---|---|
| Dense (pgvector, cosine, HNSW) | meaning, paraphrase, Hebrew | form numbers, regulation references |
| Lexical (Postgres FTS, GIN) | exact tokens: `form 4B`, `regulation 17.3` | anything phrased differently |

Dense retrieval alone misses what municipal staff actually search for. Lexical alone
misses every paraphrase. Neither has to win on its own.

**The permission predicate is written once and interpolated into both arms and the final
select.** A second retrieval path is a second way in, and it must not become a way
around the boundary. This is the single most sensitive piece of code in the system; the
tests in `api/tests/test_retrieval.py` cover each scope, archived and inactive scopes,
and the Hebrew path.

The lexical arm ORs the query terms for recall, which on its own would let a chunk in on
one incidental word — an unanswerable question would come back with confident-looking
citations. It therefore requires most of the question's content words to appear, while a
short precise query such as `regulation 17.3` still matches on its own terms.

Postgres has no Hebrew stemmer. The `english` text-search configuration tokenises Hebrew
but does not stem it, so Hebrew exact-term matching works while Hebrew paraphrase is
carried by the dense arm.

### Generation

Answers are grounded only in the retrieved chunks, streamed over SSE, with numbered
citations linking back to the source. Empty retrieval produces the standard "not covered"
reply and a row in `unanswered_questions`, which is what the content curation screen is
built from. The assistant answers in the language of the *question*, never the language
of the sources.

Greetings and thanks are answered conversationally before retrieval runs — otherwise
"hello" returns "not covered" and pollutes the unanswered-questions list.

## AI providers

Generation and embeddings are configured independently and each API key travels with its
own base URL, so one provider's key is never sent to another's endpoint. The generation
model falls back down a chain (`LLM_FALLBACK_MODELS`) when a model is rate-limited or
returns nothing — which is what makes free-tier models usable for a pilot.

**Changing `EMBEDDING_MODEL` requires re-embedding everything.** Vectors from different
models are not comparable, and mixing them degrades retrieval silently rather than
loudly: `python scripts/reembed.py --run`.

With no keys configured the whole system still runs on deterministic offline providers.
The test suite always uses those — keys in `.env` are ignored during tests — so the suite
is fast, free, hermetic, and safe to run against a developer machine holding production
credentials.

## Data model notes

- `chunks` carries denormalised `municipality_id` / `department_id` / `visibility` so the
  permission filter needs no joins to user tables in the hot path.
- `chunks.search` is a generated `tsvector` column, so the lexical index can never drift
  out of sync with the content.
- All schema changes go through Alembic. No manual DDL — the migration history is how
  production gets rebuilt.
- Admin mutations append to `audit_log`, which is never updated or deleted.

## Deviations from the scope appendix

The appendix is the contract. Where the build differs, it is on purpose, and here is the
list so nobody has to rediscover it by diffing:

| Appendix says | Built as | Why |
|---|---|---|
| Extraction via the `unstructured` library | explicit `pypdf` / `python-docx` / `python-pptx` / `openpyxl` | `unstructured` pulled in ~1.3 GB of transitive dependencies for four file types we parse directly; the image dropped from 1527 MB to 205 MB |
| LangChain for RAG orchestration | plain code | see below |
| Retrieval: cosine top-12, ≥0.35 | that, **plus** a lexical arm fused with RRF | cosine alone cannot find `form 4B` or `regulation 17.3`; the spec's threshold and top-12 are unchanged |
| Chunking: 800 tokens / 150 overlap | that, cut at paragraph boundaries, title prefixed | same budget, better boundaries |
| Empty retrieval → "not covered" | that, **except** greetings are answered conversationally first | "hello" returning "not covered" and landing in the unanswered-questions list is not the intent of the rule |
| Nightly backups, 30-day retention | **not enabled yet** | not a plan limitation — Railway schedules backups per volume and no single schedule offers 30-day nightly retention; see `RUNBOOK.md` |

The last row is the only item on this list that is outstanding rather than decided.

## What is deliberately not here

- **No vector database.** One Postgres holds application data and embeddings, so a
  permission filter and a similarity search are the same query and the same transaction.
- **No message broker.** The job queue is a table; `SKIP LOCKED` is enough at this scale
  and removes an entire service from the deployment.
- **No LangChain.** The pipeline is extract → chunk → embed → SQL → prompt, and each step
  is a few lines of explicit code. The abstraction cost exceeded its value here; revisit
  if multi-step agents or tool use are added.
