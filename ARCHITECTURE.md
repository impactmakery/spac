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

### Retrieval — the third arm: graph traversal

Dense and lexical both answer "which passage resembles this question". Neither
answers "which department runs that programme" or "what does this regulation
depend on" — questions whose answer is assembled from several documents that
share an entity.

Entities and relationships are extracted from each chunk at ingestion and stored
in `graph_entities`, `graph_mentions` and `graph_relations`. A question's named
entities seed a traversal of at most two hops, and the chunks that evidenced the
edges crossed are fused in as a third arm, weighted below the other two —
being *connected* to a question is weaker evidence than matching it.

**The rule that must not be broken:** scope lives on the **mention** and the
**relation**, never on the **entity**.

An entity is only a name. `אגף הרווחה` may be mentioned in a public circular and
in a confidential department file — two facts, different visibility. Scoping the
entity would merge them, and a traversal starting from a permitted mention could
then walk into a relationship the user must not see. Every edge therefore carries
the visibility of the chunk that evidenced it, and the filter is re-applied **on
every hop**, not once at the seed. `api/tests/test_graph.py` holds this in place.

Deleting a chunk cascades to its mentions and relations, so a deleted document
does not stay traversable — the same invariant the chunks table already has.

Extraction is behind a protocol with two implementations, chosen by
`GRAPH_EXTRACTOR`:

- `pattern` (default) — deterministic, offline, free. No API key, hermetic
  tests, and a rate-limited provider cannot break ingestion.
- `llm` — one model call per chunk at index time, falling back to `pattern` on
  any failure.

**On Hebrew the difference is not marginal.** Measured on one Hebrew municipal
paragraph:

| | Entities | Relations |
|---|---|---|
| `pattern` | 12, many fusing nouns to verbs (`נהריה אישרה`) | **0** |
| `llm` | 13, clean and typed | **9** |

Hebrew has no capitalisation to anchor on, so the pattern matcher swallows verbs
and finds no relationships at all — and a graph with no edges has nothing to
traverse, which makes the third retrieval arm inert. For a Hebrew-first corpus,
`GRAPH_EXTRACTOR=llm` is what makes the graph real rather than decorative.

The default stays `pattern` so nobody starts paying per chunk by accident.

Graph indexing and traversal both fail soft. The graph is an enhancement over
search that already works, so neither may take an answer down with it.

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
| Retrieval: cosine top-12, ≥0.35 | that, **plus** a lexical arm and a graph-traversal arm fused with RRF, then re-ranked | cosine alone cannot find `form 4B` or `regulation 17.3`, and neither arm answers questions about connections between documents; the spec's threshold and top-12 are unchanged |
| — | OCR for scanned PDFs and images | not in the appendix at all, but municipal archives are largely scanned paper, which would otherwise be silently unusable |
| Board content: exactly one of file **XOR** https link | file, link, **or a shared prompt** — and a prompt may carry a link | a prompt or agent brief is a third kind of content and the one colleagues most want to pass around; the old rule would have rejected it outright. The prompt is stored as text, so the assistant can find it |
| Uploads: PDF/DOCX/PPTX/XLSX only, everywhere | **board accepts any type**; knowledge base and department areas keep a whitelist, widened to include images and plain text | client decision, taken against my advice and recorded here. The board is the sharing surface; the other two exist to hold material the assistant reads, where a binary is dead weight. See below |

### Unrestricted board uploads, and the control that replaced the whitelist

The board accepts any file type by explicit client decision. The extension
whitelist is therefore no longer a control there, and one thing replaces it:

**Nothing outside a known-safe set is ever rendered inline.** An uploaded
`.html` or `.svg` served inline from this origin would run script against
another user's session — the platform attacking its own users, which is a
different problem from choosing to allow a file type. PDFs and images preview;
everything else downloads, with `X-Content-Type-Options: nosniff` and a
restrictive `Content-Security-Policy` so a browser cannot sniff a download back
into HTML. The browser's declared content type is never trusted, since it is
attacker-supplied and decides how the file is later served.

What is *not* mitigated, and should be stated to whoever accepts the risk: the
platform will distribute executables and archives between municipalities without
scanning them for malware. `api/tests/test_uploads_any_type.py` holds the
boundary that does exist.
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
