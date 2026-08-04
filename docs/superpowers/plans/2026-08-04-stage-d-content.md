# Stage D: Knowledge Base + Ingestion Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Files flow end-to-end: upload → R2/local storage → ingestion job → extract → chunk (800/150 tokens) → embed → `chunks` rows with permission tags → visible indexing status; delete cascades chunks + storage object in one transaction. `/knowledge` + `/knowledge/[docId]` + `/system/knowledge-base` screens.

**Architecture:** Provider pattern as in Stage B: `StorageProvider` (R2 ⇄ local disk with HMAC-signed expiring URLs served by the API) and `EmbeddingProvider` (OpenAI text-embedding-3-large truncated to 1536 dims ⇄ deterministic hash-based fake when no key). Ingestion queue = `ingestion_jobs` Postgres table consumed with `FOR UPDATE SKIP LOCKED`; worker runs as `python -m app.worker` (and inline-synchronously in tests via `run_pending_jobs(db)`).

## Global Constraints (from spec)

- Upload rules enforced server-side: extensions pdf/docx/pptx/xlsx only, mime sniff (magic bytes), ≤ 25 MB.
- chunks columns: id, source_type ('kb' | 'board' | 'department'), source_id, municipality_id, department_id, visibility ('global'|'municipality'|'department'), content, embedding vector(1536), HNSW cosine index.
- KB uploads: system admin (visibility global, municipality NULL) and municipality admins (still global visibility — KB is global; keep uploader's municipality for display). All users list/download.
- Replace keeps docId (citations stay valid), versions the storage key, re-triggers ingestion, only uploader or system admin. Delete: same actors; document + storage object + chunks in the same transaction.
- Failed extraction → status 'not_indexable', visible to uploader with retry button; 3 retries with backoff inside the worker before terminal failure.
- Statuses: pending → processing → indexed | not_indexable.

## Tasks

**D1 — Migration 3 + models:** `KbDocument(id, title, filename, storage_key, size_bytes, content_type, uploader_id, municipality_id nullable, status text default 'pending', error text nullable, created_at, updated_at)`; `Chunk(id, source_type, source_id UUID, municipality_id nullable, department_id nullable, visibility, content text, embedding Vector(1536), created_at)` + HNSW index `ix_chunks_embedding` (vector_cosine_ops) + btree on (source_type, source_id); `IngestionJob(id bigserial, source_type, source_id, payload jsonb, status 'queued'|'running'|'done'|'failed', attempts int default 0, run_after timestamptz default now, last_error, created_at, updated_at)`. Uses `pgvector.sqlalchemy.Vector`. Schema tests.

**D2 — Storage provider:** `app/services/storage.py`: `put(key, data, content_type)`, `delete(key)`, `open(key) -> bytes`, `download_url(key, filename, expires_seconds=900) -> str`. R2Provider via boto3 presigned GET; LocalDiskProvider stores under `var/files/<key>` and signs `/api/files/{key}?exp=&sig=` with HMAC(jwt_secret); router `app/routers/files.py` validates sig+expiry and streams. Tests: roundtrip, url expiry, tamper rejection.

**D3 — Upload validation:** `app/services/uploads.py`: `validate_upload(filename, content, declared_type) -> (ext, content_type)` — extension whitelist, magic-byte sniff (%PDF / PK zip for ooxml), 25 MB cap → HTTPException 415/413. Tests.

**D4 — Embeddings + chunking:** `app/rag/embeddings.py`: `embed_texts(list[str]) -> list[list[float]]` — OpenAI (model from settings, dimensions=1536, batched 100) ⇄ `FakeEmbeddings` (sha256-seeded RNG vector, deterministic, unit-norm) when no key. `app/rag/chunking.py`: `chunk_text(text, max_tokens=800, overlap=150)` using tiktoken (cl100k_base); merges short segments, splits long. Tests: determinism, overlap, token bounds.

**D5 — Extraction:** `app/rag/extract.py`: `extract_text(content: bytes, ext) -> str` — pypdf for pdf, python-docx, python-pptx, openpyxl text harvest (lighter + more portable than full `unstructured` partitioning on Windows; unstructured stays a dependency for future upgrade). Corrupt file → `ExtractionError`. Tests use tiny generated fixtures (docx/pptx/xlsx via their libs, pdf via pypdf writer).

**D6 — Ingestion queue + worker:** `app/services/ingestion.py`: `enqueue(db, source_type, source_id, visibility, municipality_id, department_id, storage_key, ext, title)` inserts job + sets doc status pending (no commit); `run_pending_jobs(db, limit=...)` claims with SKIP LOCKED, runs extract→chunk→embed→replace chunks for source, sets doc status indexed / retries (attempts<3, backoff via run_after) / not_indexable + Sentry-less log. `app/worker.py` loop: poll every 2 s. Tests: happy path creates chunks + status indexed (fake embeddings, real extraction fixture); corrupt file retries ×3 → not_indexable; delete-during-queue safe.

**D7 — KB documents API:** `app/routers/kb_documents.py`: `GET /api/kb-documents` (any user; search by title), `GET /{id}` (+ download_url), `POST` multipart (muni admin/sysadmin), `POST /{id}/replace` (uploader/sysadmin; keeps id, new storage key, re-enqueue), `DELETE /{id}` (uploader/sysadmin; doc+chunks+job cleanup in transaction, storage delete after commit), `POST /{id}/retry` (uploader/sysadmin re-enqueue). Audit uploads/replaces/deletes. Tests incl. permission matrix additions (department user cannot upload → 404) and same-transaction chunk cascade.

**D8 — /knowledge UI:** grid per appendix (icon by type, title, uploader, municipality/'Program', date, size via formatBytes, search, upload button for admins); `/knowledge/[docId]` detail: metadata, PDF inline preview (iframe of download URL), details card for others, download button, status chip (+ retry for uploader), replace/delete for uploader/sysadmin. `/system/knowledge-base`: same list + multi-upload (up to 10 files), per-file status, total storage counter. Strings he+en.

**D9 — Stage D smoke:** Playwright: sysadmin uploads a small PDF at /system/knowledge-base → status becomes Indexed (worker run inline via a test hook: run `python -c "run_pending_jobs"` between steps or run worker in background) → /knowledge shows it for the department user → detail page opens with download; replace keeps URL; delete removes row. Verify chunks in DB. Commit.

## Exit criteria

Full local gate green; upload→indexed within seconds locally (fake embeddings); delete cascade verified in test; smoke green; committed.
