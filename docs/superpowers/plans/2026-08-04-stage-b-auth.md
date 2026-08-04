# Stage B: Auth + Invitations + App Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete auth lifecycle (login/JWT/token_version, forgot/reset, accept-invite, change-password, rate limits), invitations API, and the bilingual RTL app shell + auth pages styled per the Base44 reference.

**Architecture:** API-side security core (bcrypt + HS256 JWT with token_version re-verified per request) consumed by all later stages; provider pattern for email (Resend ⇄ local outbox). Web: next-intl `[locale]` routing (he default, RTL) + NextAuth v5 credentials delegating to the API; design tokens from `docs/superpowers/specs/2026-08-04-ui-design-reference.md`.

**Tech Stack:** PyJWT, bcrypt, FastAPI dependencies; next-intl v4, next-auth v5 beta, Tailwind v4 `@theme` tokens, lucide-react, Heebo via next/font.

## Global Constraints (from spec)

- Every user-facing string in `web/messages/he.json` + `en.json` — no hardcoded literals.
- Server-side permission check on every API route; UI never the enforcement point.
- Admin mutations write to append-only `audit_log`.
- Tokens single-use, stored hashed (sha256). Invite 7-day expiry; reset 1-hour; password min 10 chars.
- Rate limits: 10 per 15 min per IP on login and forgot.
- Deactivation/reset kills sessions via `token_version` bump (≤60 s effect).
- Failed login shows a localized error that never reveals whether the email exists.
- UI matches the Base44 reference (tokens, sidebar pill nav, Heebo, warm background).

---

### Task B1: Security core (TDD)

**Files:** Create `api/app/core/security.py`; Test `api/tests/test_security.py`.

**Interfaces (Produces):**
- `hash_password(plain: str) -> str`, `verify_password(plain: str, hashed: str) -> bool`
- `create_access_token(user: User) -> str` — HS256 JWT, 30-day exp, claims: `sub` (user id str), `role`, `muni` (municipality id str | None), `depts` (list[str]), `tv` (token_version), `lang`, `name`, `email`
- `decode_token(token: str) -> dict` (raises `jwt.InvalidTokenError` family)
- `hash_token(raw: str) -> str` (sha256 hex) and `new_raw_token() -> str` (`secrets.token_urlsafe(32)`)
- FastAPI deps: `get_current_user(db, credentials) -> User` (Bearer; 401 on bad/expired token, tv mismatch, or non-active user), `require_system_admin`, `require_municipality_admin` (system admin also passes), role helpers re-exported for later stages.

**Steps:** failing tests (round-trip hash/verify; JWT claims incl. tv; tv bump ⇒ 401 through a protected test route; inactive user ⇒ 401) → implement → pass → commit.

### Task B2: Rate limiter (TDD)

**Files:** Create `api/app/core/ratelimit.py`; Test `api/tests/test_ratelimit.py`.

**Interfaces (Produces):** `RateLimiter(limit: int, window_seconds: int, clock: Callable[[], float] = time.monotonic)` with `.hit(key: str) -> bool` (False when over limit) and `.reset(key)`. Module-level `login_limiter = RateLimiter(10, 900)`, `forgot_limiter = RateLimiter(10, 900)`. In-memory sliding window (single-process deployment; documented caveat).

**Steps:** failing tests (11th hit in window blocked; expiry frees; keys independent — injected fake clock) → implement → pass → commit.

### Task B3: Email provider (TDD)

**Files:** Create `api/app/services/__init__.py`, `api/app/services/email.py`; Test `api/tests/test_email.py`.

**Interfaces (Produces):** `send_email(to: str, subject: str, html: str) -> None` via provider selected by settings: `ResendProvider` when `resend_api_key` set, else `OutboxProvider` writing `api/var/outbox/<ts>-<slug>.json` (`{"to","subject","html"}`). Test helper `read_outbox(tmp_path)` pattern: outbox dir configurable via `Settings.outbox_dir` (default `var/outbox`) so tests point it at tmp_path.

**Steps:** failing test (outbox file written with fields) → implement (resend import lazy) → pass → commit.

### Task B4: Audit service (TDD)

**Files:** Create `api/app/services/audit.py`; Test `api/tests/test_audit.py`.

**Interfaces (Produces):** `record_audit(db, *, actor_id, action: str, entity_type: str, entity_id: str | None, before: dict | None = None, after: dict | None = None) -> None` — adds row, no commit (caller's transaction).

**Steps:** failing test (row persisted with fields) → implement → pass → commit.

### Task B5: Auth router (TDD)

**Files:** Create `api/app/routers/__init__.py`, `api/app/routers/auth.py`, `api/app/schemas/__init__.py`, `api/app/schemas/auth.py`; Modify `api/app/main.py` (include router); Test `api/tests/test_auth_flow.py`.

**Interfaces (Produces):**
- `POST /api/auth/login {email, password}` → 200 `{access_token, user:{id,name,email,role,municipality_id,department_ids,language}}`; updates `last_login_at`; 401 generic `{"detail":"invalid_credentials"}`; 429 over rate limit (keyed by client IP).
- `POST /api/auth/forgot {email}` → always 200 `{"ok": true}`; creates reset token + email when account exists and active.
- `POST /api/auth/reset {token, password}` → validates single-use unexpired token, min-10 password, sets hash, marks token used, bumps `token_version`.
- `POST /api/auth/accept-invite {token, name, password, language}` → activates invited user (sets fields, status active), marks invitation used, assigns departments from `invitation.department_ids`.
- `GET /api/auth/invite-info?token=` → `{email, inviter_name, municipality_name, department_names, role}` or 404/410 for bad/used/expired.
- `POST /api/auth/change-password {current_password, new_password}` (authed) → verifies current, sets new, bumps tv, returns fresh `{access_token}`.

**Steps:** failing flow tests (login ok/wrong/inactive; rate limit 429; forgot→outbox link→reset→old token dead, old JWT dead, new login works; invite create (direct DB row)→info→accept→login; used/expired invite 410; change-password cycle) → implement → pass → commit.

### Task B6: Invitations + users/me API (TDD)

**Files:** Create `api/app/routers/invitations.py`, `api/app/routers/users.py`, `api/app/schemas/users.py`, `api/app/services/invitations.py`; Modify `api/app/main.py`; Test `api/tests/test_invitations.py`.

**Interfaces (Produces):**
- `create_invitation(db, *, email, role, municipality_id, department_ids, invited_by) -> tuple[Invitation, str]` (returns raw token; sends localized email with `{nextauth_url}/accept-invite?token=`; creates the shadow `User(status='invited')`; blocks existing active/invited email with 409).
- `POST /api/invitations` — system admin: role `municipality_admin` + municipality required; municipality admin: role `department_user` within own municipality + ≥1 department. Audit-logged `invitation.create`.
- `POST /api/invitations/{id}/resend` — regenerates token (new expiry), re-emails; scope-enforced; audit-logged.
- `GET /api/users/me` → same user payload as login; `PATCH /api/users/me {language?, digest_enabled?, name?}` → updated payload.
- Cross-scope access (muni admin inviting into another municipality, or reading another's invitation) → 404.

**Steps:** failing tests (scope matrix incl. 404s; duplicate email 409; resend regenerates; me PATCH persists) → implement → pass → commit.

### Task B7: Web i18n + design tokens

**Files:** Create `web/messages/he.json`, `web/messages/en.json`, `web/i18n/routing.ts`, `web/i18n/request.ts`, `web/middleware.ts` (next-intl), `web/app/[locale]/layout.tsx`; Modify `web/app/globals.css` (tokens from the UI reference), `web/app/layout.tsx` → delete (replaced by `[locale]` layout), `web/next.config.ts` (next-intl plugin).

**Interfaces (Produces):** `Link/redirect/usePathname/useRouter` from `web/i18n/navigation.ts`; locales `['he','en']`, default `he`; `[locale]` layout sets `dir` (`rtl` for he) + Heebo via `next/font/google`; tokens as CSS vars consumed through Tailwind v4 `@theme inline` (e.g. `--color-primary: hsl(var(--primary))`).

**Steps:** install `next-intl`; wire per next-intl v4 App Router docs; tokens + Heebo; placeholder localized home that redirects; `npm test`/`tsc`/`lint` green; commit. (Vitest: add a unit test for a `roleHome(role) -> route` helper in `web/lib/roles.ts` — `system_admin→/system/stats`, `municipality_admin→/admin/stats`, `department_user→/chat`.)

### Task B8: NextAuth v5 credentials

**Files:** Create `web/auth.ts`, `web/app/api/auth/[...nextauth]/route.ts`, `web/lib/api.ts`, `web/types/next-auth.d.ts`, `web/.env.local` (NEXTAUTH_URL/SECRET, API_BASE_URL — gitignored); Modify `web/middleware.ts` (compose next-intl + auth protection).

**Interfaces (Produces):** `auth()` returning session with `{user: {id, name, email, role, municipalityId, departmentIds, language}, apiToken}`; `apiFetch(path, init?)` server helper attaching `Authorization: Bearer <apiToken>` to `${API_BASE_URL}${path}` and throwing typed `ApiError(status)`; middleware: unauthenticated → `/login` (locale-aware), authenticated hitting `/login` or `/` → `roleHome(role)`.

**Steps:** install `next-auth@beta`; credentials provider posts to `/api/auth/login`; jwt/session callbacks carry token+user; middleware compose; gate green; commit.

### Task B9: Auth pages (Base44 style)

**Files:** Create under `web/app/[locale]/(auth)/`: `login/page.tsx`, `forgot-password/page.tsx`, `reset-password/page.tsx`, `accept-invite/page.tsx`, shared `web/components/auth-card.tsx`; strings in both message files.

**Behavior:** centered white rounded-xl card on warm gradient background, logo chip on top; login (email+password, generic error, link to forgot); forgot (always-success message); reset (`?token=`, two password fields min 10, then redirect login); accept-invite (`?token=` → GET invite-info; shows inviter/municipality/departments; name + password + language picker; on success auto-login → roleHome). All copy via next-intl in he+en.

**Steps:** implement pages + strings; manual smoke via dev servers (login error path, forgot→outbox file link→reset→login) — document results; gate green; commit.

### Task B10: App shell + profile

**Files:** Create `web/components/app-shell.tsx`, `web/components/sidebar.tsx`, `web/components/language-toggle.tsx`, `web/app/[locale]/(app)/layout.tsx` (auth-guarded, renders shell), placeholder pages: `(app)/chat/page.tsx`, `(app)/knowledge/page.tsx`, `(app)/board/page.tsx`, `(app)/municipality/page.tsx`, `(app)/profile/page.tsx`, `admin/stats/page.tsx`, `system/stats/page.tsx` (placeholders say "coming in later stage" via i18n); strings in both files.

**Behavior:** sidebar per role (links per scope appendix "App shell & navbar" row), Base44 styling (white sidebar, teal pill active, logo chip, bottom profile chip + language toggle + sign out), hamburger drawer under 768px. Language toggle: shows the OTHER language, on click PATCHes `/api/users/me {language}` then navigates to the same path in the other locale. `/profile`: display name (editable), email/municipality/departments read-only, language, digest toggle, change-password form (calls API, then signs out/in with new token or updates session).

**Steps:** implement; vitest for sidebar link-set-per-role helper (`web/lib/nav.ts`); manual smoke he+en incl. RTL flip; gate green; commit.

## Stage B exit criteria

- Full auth lifecycle works in the browser against the running API with outbox emails (invite → accept → login → change password → reset → deactivate kills session).
- Access-control tests for invitations pass; all previous tests still green.
- Shell renders in he (RTL, sidebar right) and en (LTR, sidebar left) matching the Base44 look.
- Full local gate green (api: ruff/mypy/pytest; web: tsc/eslint/vitest). All committed.
