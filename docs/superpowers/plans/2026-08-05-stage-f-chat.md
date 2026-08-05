# Stage F: Chat Assistant (Permission-Filtered RAG) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A working chat assistant grounded only in platform content the asking user may see: retrieval with the permission filter inside the SQL, SSE-streamed answers with numbered citations, private conversation history, unanswered-question logging, and the 30-question grounding eval.

**Architecture:** `app/rag/retrieval.py` (SQL + permission filter), `app/rag/generation.py` (LLM provider: OpenAI ⇄ deterministic fake that composes from retrieved chunks), `app/routers/chat.py` (SSE endpoint + conversations CRUD). Web: `/chat` and `/chat/[conversationId]` reading the SSE stream directly from the API with the session's bearer token.

## Global Constraints (hard requirements from the spec)

- Retrieval: top 12 by cosine, drop below 0.35 similarity, and the WHERE clause enforces
  `visibility='global' OR municipality_id = :user_muni OR department_id IN (:user_depts)`.
  **Never filter after retrieval — filter IN the query.**
- Answer only from retrieved chunks; answer in the language of the question.
- Stream via SSE; numbered citations linking to the source document / board item / department file.
- Empty retrieval ⇒ standard "not covered by the available material" reply + row in `unanswered_questions`. An answer with zero retrievable sources must be impossible by construction.
- Conversations are private to the user — no admin surface exposes chat content, including the system admin.
- Context window = last 10 exchanges; history paginated at 50 messages.
- Per-user rate limit 60 messages/hour. Retrieval SQL, chunk ids, similarity scores, and the final prompt logged per message, retained 90 days.
- Archived departments and deactivated municipalities must be excluded from retrieval.

## Tasks

**F1 — Migration 5 + models:** `Conversation(id, user_id CASCADE, title, created_at, updated_at)`; `Message(id, conversation_id CASCADE, role 'user'|'assistant', content, citations JSONB, created_at)`; `MessageDebug(id, message_id CASCADE, retrieval_sql, chunk_ids JSONB, scores JSONB, prompt, created_at)` (90-day retention, purged by cron in Stage G); `UnansweredQuestion(id, user_id, municipality_id, question, created_at)`. Schema tests.

**F2 — Retrieval (TDD):** `retrieve(db, *, query_embedding, user, limit=12, min_similarity=0.35) -> list[RetrievedChunk]`. Single SQL statement: cosine distance ordering on the HNSW index, permission predicate inline, joins excluding archived departments and inactive municipalities. Tests: global-only user sees global chunks; municipality member sees own-municipality chunks but not another's; department member sees own department; **cross-department leak test returns nothing**; below-threshold chunks dropped; archived department excluded.

**F3 — Generation provider (TDD):** `app/rag/generation.py` — `stream_answer(question, chunks, history) -> Iterator[str]`. OpenAI path uses `LLM_MODEL` with a system prompt that forbids outside knowledge and requires citation markers `[1]`, `[2]`. Fake path (no API key) composes a deterministic answer from the retrieved chunk texts with the same citation markers, in the question's language (Hebrew if the question contains Hebrew letters). Tests: citations present, fake path deterministic, empty chunk list never reaches the model.

**F4 — Chat API (TDD):** 
- `GET /api/conversations` (own only), `POST /api/conversations`, `DELETE /api/conversations/{id}` (own only, hard delete), `GET /api/conversations/{id}/messages?before=` (50/page).
- `POST /api/chat/{conversation_id}/messages` → SSE stream: `event: token` chunks, then `event: citations` with the source list, then `event: done`. Persists both messages, writes MessageDebug, logs unanswered when retrieval is empty, auto-titles the conversation from the first question, enforces 60/hour.
- Another user's conversation → 404 (including for the system admin).
- Tests: full flow with fake providers; rate limit 429; cross-user 404; unanswered logging; citations reference real sources.

**F5 — Chat UI:** `(app)/chat/page.tsx` (conversation rail + empty state with 4 sample questions drawn from KB titles) and `(app)/chat/[conversationId]/page.tsx`. Client component streams via `fetch` + `ReadableStream` against `${API_BASE_URL}/api/chat/...` with the bearer token from a server action that returns the session token. Renders streaming assistant bubbles, numbered citation chips linking to `/knowledge/[id]` or `/board/[id]`, permanent notice that answers come only from platform content, Enter-to-send / Shift+Enter newline. Strings he+en.

**F6 — RAG grounding eval:** `api/tests/test_rag_eval.py` — seeds fixture documents across scopes, then runs 30 questions (20 answerable → must cite the correct source; 10 unanswerable → must return the not-covered reply), including a cross-department leak question that must return not-covered. Marked slow but part of the default suite locally.

**F7 — Stage F smoke:** Playwright — ask a question grounded in the seeded KB document, verify the streamed answer renders with a citation chip that navigates to the document; ask an unanswerable question and verify the not-covered response plus the unanswered_questions row.

## Exit criteria

Full local gate green (ruff, mypy, pytest incl. eval + matrix; tsc, eslint, vitest); chat works end-to-end in the browser on fake providers; cross-department leak test green; committed.
