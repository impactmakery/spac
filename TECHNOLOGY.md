# Technology

Everything this platform is built from, what each piece is for, and why it was chosen
over the obvious alternative. `ARCHITECTURE.md` explains how the parts fit together;
this is the parts list.

Versions are the floor declared in `api/requirements.txt` and `web/package.json` — those
files are the source of truth if the two ever disagree.

## Backend — Python 3.12

| Package | Version | What it does |
| --- | --- | --- |
| FastAPI | ≥0.115 | HTTP framework. Every permission check lives here. |
| Uvicorn | ≥0.30 | ASGI server. |
| SQLAlchemy | ≥2.0 | ORM and query builder. Retrieval drops to raw SQL where the permission filter has to be inside the query. |
| Alembic | ≥1.13 | Migrations, applied on container boot. No manual DDL. |
| psycopg | ≥3.2 | PostgreSQL driver. |
| pgvector | ≥0.3 | Vector column type and distance operators. |
| pydantic-settings | ≥2.4 | Configuration from environment, with `.env` for local work. |
| PyJWT | ≥2.9 | Session tokens. |
| bcrypt | ≥4.2 | Password hashing. |
| tiktoken | ≥0.7 | Token counting, so chunks are 800 tokens rather than 800 characters. |
| python-multipart | — | Multipart uploads; FastAPI needs it at runtime. |
| email-validator | ≥2.0 | Required by Pydantic's `EmailStr`. |

## Frontend — Next.js 16, React 19, TypeScript 5

| Package | Version | What it does |
| --- | --- | --- |
| Next.js | 16.3 | App Router. Pages fetch on the server, so the browser never holds an API token. |
| React | 19.2 | — |
| next-intl | ≥4.13 | Hebrew and English. Every user-facing string lives in `messages/`. |
| NextAuth (Auth.js) | v5 beta | Session cookie; credentials are verified by the API, never in the frontend. |
| Tailwind CSS | v4 | Right-to-left comes from logical properties, so both languages share one stylesheet. |
| lucide-react | ≥1.28 | Icons. |
| clsx | ≥2.1 | Conditional class names. |
| Vitest | ≥4.1 | Unit tests. |
| ESLint, TypeScript | 9, 5 | `tsc --noEmit` and lint both gate CI. |

## Reading documents

One library per format, no heavyweight document toolkit.

| Package | Format |
| --- | --- |
| pypdf ≥4.0 | PDF text layer |
| python-docx ≥1.1 | Word |
| python-pptx ≥0.6 | PowerPoint |
| openpyxl ≥3.1 | Excel |
| Pillow ≥10.0 | Images |

### OCR

Used only when the libraries above return implausibly little text — a scanned PDF with no
text layer, or an Office file whose content is pictures.

| Package | Role |
| --- | --- |
| Tesseract OCR | The engine. Installed in the container with Hebrew, Arabic and English language packs. Set by `OCR_LANGUAGES`; any language added there needs its apt package in the Dockerfile, and a test enforces that. |
| pytesseract ≥0.3.13 | Python binding. |
| pypdfium2 ≥4.30 | Rasterises PDF pages so Tesseract has something to read. |

**pypdfium2 rather than PyMuPDF.** PyMuPDF is AGPL, which would put a copyleft obligation
on a commercial product. pypdfium2 is BSD and does the same job here.

**Arabic matters here.** Two of the municipalities are Arabic-speaking towns. The
container originally shipped Hebrew and English only, so every scanned or picture-based
Arabic document read as nothing at all — OCR running correctly and recognising no words,
which is indistinguishable from a document that has none.

**Tesseract is free and runs locally**, so OCR costs no API money — only worker CPU, which
is why scanned documents are the slow part of any bulk load. Its Hebrew is good on clean
printed text and weak on handwriting, poor scans, and stylised design work. If quality
matters more than cost later, a cloud OCR (Google Document AI, Azure Document
Intelligence) is markedly better on Hebrew at per-page pricing.

## Infrastructure

| Service | Role |
| --- | --- |
| PostgreSQL 16 + pgvector | Application data *and* embeddings, one database, HNSW index. |
| Cloudflare R2 (boto3 ≥1.34) | Uploaded files. S3-compatible; uploads go through the server, downloads use short-lived signed links. |
| Railway | API, ingestion worker, cron. Amsterdam region, chosen for latency to Israel. |
| Vercel | The web app. |
| Resend ≥2.0 | Invitations, password resets, weekly digest. Sending from `updates.impactmakery.com`. |
| Sentry SDK ≥2.0 | Installed and wired in, **not yet configured** — no DSN set, so nothing is reported. Open item. |

## AI

Three separate jobs, and only one of them costs money.

| Job | Provider | Model | Cost |
| --- | --- | --- | --- |
| Answering questions | OpenRouter | `google/gemma-4-26b-a4b-it:free`, with a fallback chain | free tier |
| Understanding documents for search | OpenAI | `text-embedding-3-large` | paid, per document |
| Building the knowledge graph | none | regex pattern matching | free |

Embedding is charged when a document is uploaded, not when someone asks a question — the
whole 344-document municipal load cost roughly $0.20. Asking questions is currently free
because the answering models are on OpenRouter's free tier, which is also why there is a
fallback chain: when one model is rate-limited the request falls through to the next, and
the user sees a slower answer rather than an error.

**Answer quality is capped by those free models.** Finding the right passages and writing
the answer are separate jobs; the retrieval side is thoroughly tested, the writing side
runs on a free model. Moving to a paid model is a one-line configuration change.

**Graph extraction was switched from a language model to pattern matching** during the
first bulk load: building the graph with a model meant roughly ten thousand calls against
a daily free quota. Pattern matching finds entities but few relationships, especially in
Hebrew, which has no capitalisation to lean on. Search, ranking and citations are
unaffected — the graph is a third way of finding passages, not the only one. Point
`GRAPH_EXTRACTOR` back at a funded model and re-run `scripts/reembed.py --run` to rebuild
it properly.

**Changing `EMBEDDING_MODEL` requires re-embedding everything.** Vectors from different
models are not comparable and mixing them degrades retrieval silently.

## Search

No external search service. Three methods over the same Postgres, fused by Reciprocal
Rank Fusion and then re-ranked:

- **Dense** — pgvector cosine similarity over an HNSW index
- **Lexical** — PostgreSQL full-text search with a GIN index
- **Graph** — traversal of entities and relations extracted at index time

The permission filter is inside every arm of that query rather than applied to its
results. See `ARCHITECTURE.md` for why that distinction is the whole design.

## Development and CI

| Tool | Role |
| --- | --- |
| ruff | Lint and import ordering. |
| mypy | Type checking, API only. |
| pytest, pytest-asyncio | API tests. The access-control suite must pass on every PR. |
| pgserver ≥0.1.4 | Embedded PostgreSQL, so the suite runs without Docker. |
| GitHub Actions | web: `tsc --noEmit`, eslint, vitest · api: ruff, mypy, pytest. |
| Docker Compose | Local Postgres + pgvector. |

The test suite runs on deterministic offline providers — keys in `.env` are ignored — so
it is fast, free, hermetic, and safe to run on a machine holding production credentials.

## Deliberately not used

Explained in full under "What is deliberately not here" in `ARCHITECTURE.md`:

- **No vector database.** One Postgres, so a permission filter and a similarity search
  are the same query and the same transaction.
- **No message broker.** The job queue is a table claimed with `SKIP LOCKED`.
- **No LangChain**, despite the original plan naming it. The pipeline is extract → chunk
  → embed → SQL → prompt, each step a few explicit lines. Worth revisiting if multi-step
  agents or tool use are added.
