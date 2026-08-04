# Stage E: Boards + Department Areas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Global board, municipality boards, item detail with comments/likes, publish dialog, department areas (files + posts) — all scope-enforced, all content flowing into the ingestion pipeline with correct visibility tags.

**Architecture:** Follows Stage B–D conventions. Board/department content enqueues ingestion jobs exactly like KB docs (`source_type` 'board' / 'department'; visibility 'global'/'municipality'/'department'). Full-text search via a generated tsvector column using the `simple` config (Postgres has no Hebrew stemmer; `simple` tokenizes Hebrew + English acceptably — documented decision).

## Global Constraints (from spec)

- Publish: title ≤120 required, description ≤2000 optional, category required (managed list), content = exactly ONE of file (pdf/docx/pptx/xlsx ≤25 MB) or https link, destination = global | own municipality. Live immediately.
- Municipality item fetched by non-member → 404. All list queries filtered server-side by scope.
- Delete rules: author own items; municipality admin any item on their municipality board AND their municipality's members' items on the global board; system admin anywhere. Deletion removes item + comments + file + chunks (same transaction; storage after commit). Audited for admin deletions.
- Comments: flat, newest last, ≤1000 chars; authors delete own; admins delete any in scope.
- Edit (author only): title/description/category — file is replace-by-delete.
- Board item ingestion: file content + description; visibility global or municipality (+municipality_id).
- Department areas: members + their municipality admin + system admin; anyone else → 404 (per CLAUDE.md 404 rule; appendix's "403" row resolved to 404 in the design spec). Files (same upload rules, visibility 'department') and lightweight text posts ≤2000 with comments, no likes/categories. Posts are also retrievable content? Spec: "All content is retrievable by the assistant for members only" — index posts too (source 'department', text = post body).
- Sidebar department links already exist; board pages must show inactive-author badge later (offboarding shows 'inactive' badge — include author status in payloads).

## Tasks

**E1 — Migration 4 + models:** `BoardItem(id, title, description, category_id FK RESTRICT, scope 'global'|'municipality', municipality_id nullable(required when scope=municipality), author_id, link_url nullable, filename/storage_key/size_bytes/content_type nullable, indexing_status 'none'|'pending'|'processing'|'indexed'|'not_indexable', created_at, updated_at, search tsvector GENERATED (simple: title+description))` + GIN index; `BoardComment(id, item_id CASCADE, author_id, body ≤1000, created_at)`; `BoardLike(item_id, user_id, PK both, created_at)`; `DepartmentFile(id, department_id CASCADE, uploader_id, filename, storage_key, size_bytes, content_type, status(indexing), error, created_at)`; `DepartmentPost(id, department_id CASCADE, author_id, body ≤2000, created_at)`; `DepartmentPostComment(id, post_id CASCADE, author_id, body ≤1000, created_at)`. Ingestion `_set_source_status` extended for 'board'→BoardItem.indexing_status and 'department'→DepartmentFile.status (posts have no status).

**E2 — Boards API (`app/routers/board_items.py`):**
- `GET /api/board-items?scope=global|municipality&search=&category_id=&sort=newest|liked&page=` (30/page; returns rows + `has_more`; row: id, title, description, category {id,name_he,name_en}, author {id,name,municipality_name,status}, has_file/filename/size, link_url, like_count, comment_count, liked_by_me, created_at, can_edit, can_delete)
- `POST /api/board-items` multipart (file variant) or JSON (link variant): validation per constraints; enqueue ingestion (file → extract; link/no-file → description text); scope municipality forced to actor's municipality (sysadmin may pass one for global? sysadmin publishes global or any muni board — allow explicit municipality_id for sysadmin).
- `GET /{id}` detail (+ comments list + download_url when file) — scope check → 404.
- `PATCH /{id}` author-only: title/description/category. `DELETE /{id}` per delete rules (cascade chunks/comments/likes/file; audit when actor ≠ author).
- `POST /{id}/like` toggle → {liked, like_count}. `POST /{id}/comments` {body} → comment; `DELETE /{id}/comments/{comment_id}` author/admin-in-scope.
- Search: `search @@ plainto_tsquery('simple', :q)` OR ilike fallback on title+description.

**E3 — Department areas API (`app/routers/department_content.py`):** membership dep (`_require_department_access(db, user, dept_id)` → member | muni admin of its municipality | sysadmin, else 404); `GET/POST /api/departments/{id}/files` (multipart, ingestion visibility='department'), `DELETE /files/{file_id}` (uploader/admins; cascade chunks+storage); `GET/POST /api/departments/{id}/posts` (body ≤2000; enqueue text index via a lightweight 'department' post source — store post body as its own chunk source: source_type='department', source_id=post.id), `DELETE /posts/{post_id}` (author/admins, cascade chunks+comments), `POST /posts/{post_id}/comments` + `DELETE .../{comment_id}`.
Note: text-only sources (posts, link-only board items) index WITHOUT storage: extend ingestion payload with optional `"text"` — when present skip storage/extract and chunk the text directly.

**E4 — Access matrix additions:** foreign municipality board item GET/PATCH/DELETE → 404; foreign department files/posts GET/POST → 404; department user delete other's item → 404/403-check; anonymous → 401.

**E5 — Boards UI:** `components/board/` — `board-page.tsx` (toolbar: publish button, search, category filter, sort select; card grid; load-more), `publish-dialog.tsx` (all fields + validation + file XOR link toggle), `item-card.tsx` (pastel category chip — deterministic hue by category id; counts; author+date). Pages: `(app)/board/page.tsx` (scope=global), `(app)/municipality/page.tsx` (scope=municipality, header names the municipality), `(app)/board/[itemId]/page.tsx` (detail + comments + like + edit dialog + delete + leaving-platform confirm for external links). Strings he+en.

**E6 — Department area UI:** `(app)/departments/[deptId]/page.tsx` — header with department name, two tabs: Files (upload button, rows like KB with status chip + delete) and Posts (composer ≤2000, post list newest first with comments + delete). Strings he+en.

**E7 — Stage E smoke:** Playwright — publish link item to global board (category), publish file item to municipality board, like+comment, verify muni scoping (other-muni admin can't see item), department file upload + post + comment; verify chunks rows for board file, board description, department file, department post. Full gates green; commit.

## Exit criteria

Both boards + department areas fully functional in the browser; ingestion tagging correct per visibility (verified in DB); access matrix green; all gates green; committed.
