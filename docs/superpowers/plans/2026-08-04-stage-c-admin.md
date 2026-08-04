# Stage C: Admin Screens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** All municipality-admin and system-admin management screens working end-to-end: municipalities, categories, users (both scopes), departments with archive lifecycle — scope-enforced APIs, audit logging, and Base44-styled UIs.

**Architecture:** Follows Stage B conventions exactly: routers depend on `require_system_admin` / `require_municipality_admin` / `get_current_user` from `app.core.security`; cross-scope reads return 404; admin mutations call `record_audit`; UI pages are server components fetching via `apiFetch` + client components for dialogs/forms using server actions in `(app)/admin|system/actions.ts`.

**Tech Stack:** unchanged (FastAPI + SQLAlchemy; Next 16 + next-intl).

## Global Constraints (from spec)

- Cross-scope reads → 404 (never 403 for resources; role-gate mismatches also 404 per Stage B).
- Deactivation bumps `token_version` (sessions die ≤60 s). Reactivation restores same departments.
- Department delete = archive (status='archived', `archive_expires_at = now + 90 days`), type-name-to-confirm in UI; restore clears both; department names unique among active per municipality (DB partial index from Stage A).
- Municipality has NO delete — deactivate only (blocks its users' logins via login check + hides content later stages). Reversible.
- Categories: bilingual names (name_he, name_en), global, item counts, no hard delete while items exist — merge-into is the removal path (board_items arrive Stage E; merge updates a `category_id` FK that exists then — for now merge just deletes the source after asserting zero items).
- Last-admin guard: the system admin cannot demote themselves.
- Users with zero departments flagged for reassignment (red) on /admin/users.
- Every user-facing string in `he.json` + `en.json`.

---

### Task C1: Migration 2 — categories (TDD)

**Files:** `api/app/models/base.py` (+Category), `api/alembic/versions/0002_categories.py`, test in `api/tests/test_schema.py`.

**Produces:** `Category(id: UUID, name_he: Text unique, name_en: Text unique, created_at)`.

### Task C2: Municipalities API (TDD)

**Files:** `api/app/routers/municipalities.py`, `api/tests/test_municipalities.py`; wire in `main.py`.

**Produces (all system-admin-only; non-sysadmin → 404):**
- `GET /api/municipalities` → `[{id, name, status, admin_names: [str], user_count, department_count, created_at}]`
- `POST /api/municipalities {name}` → 201 (live immediately); duplicate active name → 409
- `PATCH /api/municipalities/{id} {name?}` → rename, audit `municipality.rename` with before/after
- `POST /api/municipalities/{id}/deactivate` + `/reactivate` → status flip, audit; deactivate bumps token_version of ALL its users (login also rejects users of inactive municipalities — add check to login + get_current_user)

### Task C3: Categories API (TDD)

**Files:** `api/app/routers/categories.py`, `api/tests/test_categories.py`.

**Produces:** `GET /api/categories` (any authed user → `[{id, name_he, name_en, item_count: 0-for-now}]`), `POST` / `PATCH /{id}` (rename) / `POST /{id}/merge-into/{target_id}` — system admin only, audited. Merge with items is completed in Stage E; now it re-parents nothing and deletes the source.

### Task C4: Departments API (TDD)

**Files:** `api/app/routers/departments.py`, `api/tests/test_departments.py`.

**Produces (municipality admin, own scope; system admin any scope via ?municipality_id=):**
- `GET /api/departments?status=active|archived` → `[{id, name, status, member_count, file_count: 0, created_at, archive_expires_at}]`
- `POST {name}` → 201; duplicate active name in muni → 409
- `PATCH /{id} {name}` → rename, audited
- `POST /{id}/archive` → archived + expires now+90d, audited; `POST /{id}/restore` → active, clears expiry, audited; restore hitting a name conflict → 409
- Cross-municipality access → 404. Users left with zero departments surface via C5's zero-departments flag.

### Task C5: Admin users API (TDD)

**Files:** `api/app/routers/admin_users.py`, `api/tests/test_admin_users.py`.

**Produces:**
- `GET /api/admin/users?search=&department_id=&status=&municipality_id=&role=` — muni admin: own municipality only (municipality_id forced); sysadmin: all + filters. Rows: `{id, name, email, role, status, municipality_id, municipality_name, departments: [{id,name}], last_login_at, has_zero_departments}` (status Invited derived from user.status='invited')
- `PUT /api/admin/users/{id}/departments {department_ids}` — reassign, scope-enforced, audited
- `POST /api/admin/users/{id}/deactivate` — bumps token_version, status inactive, audited; `/reactivate` restores (same departments retained)
- `POST /api/admin/users/{id}/promote` / `/demote` — sysadmin only; promote → municipality_admin, demote → department_user; self-demote → 409 (last-admin guard); audited
- Invitation resend already exists (`/api/invitations/{id}/resend`); expose pending invitation id on the user row (`invitation_id` when status invited).

### Task C6: Access-control matrix seed test

**Files:** `api/tests/test_access_matrix.py`.

Parametrized: for each (actor role) × (foreign resource endpoint) assert 404/401 — municipality admin hitting other municipality's departments/users/invitations; department user hitting all admin endpoints; anonymous hitting everything → 401. This file grows in later stages.

### Task C7: /system/municipalities UI

Table per appendix row 47 (name, admins, user count, dept count, created; Add by name; Rename; Invite admin (email); Deactivate/Reactivate with confirm). Server page + client dialogs; strings he+en.

### Task C8: /system/categories UI

List with item counts + Add / Rename (bilingual fields) / Merge-into select; no delete while items exist (merge only). Strings he+en.

### Task C9: /admin/departments UI

Active tab: cards (name, member count, created) with Rename + Delete (type-name-to-confirm → archive). Archived tab: days-remaining counter + Restore (+ Download-all placeholder disabled until Stage D files exist). Create form. Strings he+en.

### Task C10: /admin/users + /system/users UI

Shared table component: name, email, department chips, status badge, last login; actions per role: Invite dialog (email + departments multi-select; sysadmin variant: role/municipality), Edit departments, Deactivate/Reactivate, Re-send invite; zero-departments rows flagged red; search + filters. /system/users adds municipality/role filters + Promote/Demote. Strings he+en.

### Task C11: Stage C smoke test

Playwright: as sysadmin — create municipality, invite muni admin (accept via outbox link), create categories; as new muni admin — create departments, invite department user (accept), edit their departments, deactivate/reactivate; verify archived department lifecycle; verify muni admin cannot see /system/*. Commit.

## Exit criteria

Full local gate green (api ruff/mypy/pytest incl. matrix; web tsc/eslint/vitest); Playwright smoke passes; every mutation visible in audit_log; all committed.
