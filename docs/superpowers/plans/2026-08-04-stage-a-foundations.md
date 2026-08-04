# Stage A: Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A running local platform skeleton — Python 3.12 env, embedded Postgres 16 + pgvector, FastAPI core with DB-checked health, Alembic migration 1, pytest harness against real Postgres, vitest harness, CI workflow, real secrets.

**Architecture:** Sync SQLAlchemy 2.0 (Mapped/mapped_column) over psycopg3; FastAPI app factory; embedded Postgres managed by `api/scripts/dev_db.py` for dev and by a session-scoped pytest fixture for tests (template-database cloning for per-test isolation). Web keeps the create-next-app scaffold and gains vitest.

**Tech Stack:** uv, Python 3.12, FastAPI, SQLAlchemy 2, Alembic, psycopg3, pgserver (fallback: portable PostgreSQL zip + pgvector DLL), Next.js 15, vitest.

## Global Constraints (from spec — apply to every task)

- All schema changes through Alembic. No manual DDL.
- DB naming: snake_case tables/columns; UUID PKs (`uuid4`) except `audit_log` (bigserial); timestamps are `timestamptz` named `created_at` etc.
- Roles exactly: `system_admin`, `municipality_admin`, `department_user`. Languages exactly: `he`, `en`.
- `audit_log` is append-only — no code path may UPDATE or DELETE rows.
- Root `.env` is the single env file for the API (loaded via pydantic-settings).
- Commit at the end of every task with a descriptive message.

---

### Task A1: Python 3.12 toolchain

**Files:** none created in repo (env only; `.gitignore` already covers `.venv`).

- [ ] Install uv (user-level, no admin): `pip install uv` (system Python is fine as bootstrap; verify with `uv --version`).
- [ ] `cd api && uv venv .venv --python 3.12` (uv downloads CPython 3.12 if absent). Verify: `.venv\Scripts\python --version` → `Python 3.12.x`.
- [ ] `uv pip install -r requirements.txt --python .venv\Scripts\python`. If **only** the `unstructured` line fails to build on Windows: edit `api/requirements.txt`, replace that line with `# unstructured[docx,pptx,xlsx,pdf]>=0.15  # deferred to Stage D (Windows build issue); extractor fallback per roadmap`, re-run install, and note it in the Stage A completion report.
- [ ] Commit any requirements.txt change: `git commit -am "chore: adjust api requirements for local install"` (skip if no change).

### Task A2: Embedded Postgres 16 + pgvector

**Files:**
- Create: `api/scripts/dev_db.py`
- Modify: `.gitignore` (add `api/var/`)

**Interfaces:**
- Produces: a running Postgres with database `tah` and `vector` extension; `DATABASE_URL` in `.env` updated in place to point at it. Later tasks only read `DATABASE_URL`.

- [ ] `uv pip install pgserver --python .venv\Scripts\python`. **If no Windows wheel exists**, fallback: download the EDB "binaries only" PostgreSQL 16 zip into `api/var/pgsql/` (no admin), download a prebuilt pgvector Windows release (vector.dll + vector.control + SQL files) into its `lib/` + `share/extension/`, and adapt `dev_db.py` to call `initdb`/`pg_ctl` from that directory instead of pgserver. The script's contract (below) stays identical.
- [ ] Write `api/scripts/dev_db.py`:

```python
"""Start (or reuse) the local dev Postgres and sync DATABASE_URL in .env.

Usage: python scripts/dev_db.py [stop]
"""
import re
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
ROOT = API_DIR.parent
PGDATA = API_DIR / "var" / "pgdata"


def main() -> None:
    import pgserver

    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        pgserver.get_server(PGDATA).cleanup()
        print("stopped")
        return

    server = pgserver.get_server(PGDATA, cleanup_mode=None)
    if "tah" not in server.psql("SELECT datname FROM pg_database"):
        server.psql("CREATE DATABASE tah")
    uri = server.get_uri(database="tah")
    url = uri.replace("postgresql://", "postgresql+psycopg://")
    env_path = ROOT / ".env"
    text = env_path.read_text(encoding="utf-8")
    text = re.sub(r"^DATABASE_URL=.*$", f"DATABASE_URL={url}", text, flags=re.M)
    env_path.write_text(text, encoding="utf-8")
    # vector extension lives per-database
    import psycopg

    with psycopg.connect(uri) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    print(url)


if __name__ == "__main__":
    main()
```

  (Adjust to pgserver's actual API surface after install — `get_server`, `get_uri`, `psql` names verified against its README; keep the contract: idempotent start, ensure `tah` DB + `vector` extension, rewrite `DATABASE_URL` in `.env`, print the URL.)
- [ ] Run it: `.venv\Scripts\python scripts/dev_db.py`. Verify output URL, and `SELECT extname FROM pg_extension` includes `vector` (one-liner via psycopg).
- [ ] Add `api/var/` to root `.gitignore`. Commit: `chore: embedded dev Postgres with pgvector (dev_db script)`.

### Task A3: API core — config, db, health with DB check (TDD)

**Files:**
- Create: `api/app/core/__init__.py`, `api/app/core/config.py`, `api/app/core/db.py`
- Modify: `api/app/main.py`
- Create: `api/tests/__init__.py`, `api/tests/conftest.py`, `api/tests/test_health.py`
- Create: `api/pyproject.toml` (ruff/mypy/pytest config)

**Interfaces:**
- Produces: `get_settings() -> Settings` (cached; fields: `database_url: str`, `jwt_secret: str`, `nextauth_url: str`, `api_base_url: str`, `openai_api_key: str`, `llm_model: str`, `embedding_model: str`, `r2_account_id/access_key_id/secret_access_key/bucket: str`, `resend_api_key: str`, `email_from: str`, `cron_secret: str` — all defaulting to `""` except `database_url`); `get_db()` FastAPI dependency yielding a `Session`; `create_app() -> FastAPI`; test fixtures `client` (TestClient with fresh DB) and `db` (Session on fresh DB).

- [ ] Write `api/pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.12"
strict = false
check_untyped_defs = true
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] Write failing test `api/tests/test_health.py`:

```python
def test_health_reports_ok_and_db(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
```

- [ ] Write `api/tests/conftest.py` — session-scoped embedded PG + per-test database from template:

```python
import uuid
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

TEMPLATE = "tah_test_template"


@pytest.fixture(scope="session")
def pg_uri() -> str:
    """Plain postgres URI to the server's maintenance DB (no +psycopg)."""
    import os

    if os.environ.get("TEST_PG_URI"):  # CI: service container
        return os.environ["TEST_PG_URI"]
    from pathlib import Path

    import pgserver

    pgdata = Path(__file__).resolve().parents[1] / "var" / "pgdata_test"
    server = pgserver.get_server(pgdata, cleanup_mode=None)
    return server.get_uri()


@pytest.fixture(scope="session")
def template_db(pg_uri: str) -> str:
    from alembic import command
    from alembic.config import Config
    from pathlib import Path

    with psycopg.connect(pg_uri, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{TEMPLATE}"')
        conn.execute(f'CREATE DATABASE "{TEMPLATE}"')
    tmpl_uri = pg_uri.rsplit("/", 1)[0] + f"/{TEMPLATE}"
    with psycopg.connect(tmpl_uri, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", tmpl_uri.replace("postgresql://", "postgresql+psycopg://"))
    command.upgrade(cfg, "head")
    return tmpl_uri


@pytest.fixture()
def db_url(pg_uri: str, template_db: str) -> Iterator[str]:
    name = f"tah_t_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(pg_uri, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}" TEMPLATE "{TEMPLATE}"')
    yield pg_uri.rsplit("/", 1)[0] + f"/{name}"
    with psycopg.connect(pg_uri, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE "{name}" (FORCE)')


@pytest.fixture()
def engine(db_url: str):
    eng = create_engine(db_url.replace("postgresql://", "postgresql+psycopg://"))
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine) -> Iterator[Session]:
    with sessionmaker(bind=engine)() as session:
        yield session


@pytest.fixture()
def client(engine) -> Iterator[TestClient]:
    from app.core.db import get_db
    from app.main import create_app

    app = create_app()

    def override() -> Iterator[Session]:
        with sessionmaker(bind=engine)() as session:
            yield session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
```

  Note: `template_db` runs Alembic; until Task A4 creates the migration, `command.upgrade` on an empty script directory is a no-op — the health test must pass **before** A4 exists. Alembic scaffolding is therefore created in THIS task (empty versions dir), migration content in A4.
- [ ] Run: `.venv\Scripts\python -m pytest tests/test_health.py -v` → FAIL (no `create_app`).
- [ ] Write `api/app/core/config.py`:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = ""
    jwt_secret: str = ""
    nextauth_url: str = ""
    api_base_url: str = ""
    openai_api_key: str = ""
    llm_model: str = "gpt-4.1"
    embedding_model: str = "text-embedding-3-large"
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    resend_api_key: str = ""
    email_from: str = ""
    cron_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] Write `api/app/core/db.py`:

```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


_session_factory: sessionmaker[Session] | None = None


def get_db() -> Iterator[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=_engine())
    with _session_factory() as session:
        yield session
```

- [ ] Rewrite `api/app/main.py` as an app factory; `/health` runs `SELECT 1` through the session dependency and reports `{"status": "ok", "db": "ok"}` (db `"error"` + status `"degraded"` on failure). Keep the module-level `app = create_app()` for uvicorn.

```python
from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db


def create_app() -> FastAPI:
    app = FastAPI(title="Tomorrow Agent Hub API")

    @app.get("/health")
    def health(db: Session = Depends(get_db)) -> dict:
        try:
            db.execute(text("SELECT 1"))
            db_state = "ok"
        except Exception:
            db_state = "error"
        return {"status": "ok" if db_state == "ok" else "degraded", "db": db_state}

    return app


app = create_app()
```

- [ ] Create Alembic scaffolding now (so conftest works): `cd api && .venv\Scripts\python -m alembic init alembic`; edit `alembic/env.py` to import `from app.core.db import Base` and `from app import models  # noqa: F401` (models package created in A4 — create an empty `api/app/models/__init__.py` now), set `target_metadata = Base.metadata`, and read the URL from config override or `get_settings().database_url`.
- [ ] Run: `pytest tests/test_health.py -v` → PASS.
- [ ] Commit: `feat(api): app factory, settings, db session, DB-checked health; test harness on embedded Postgres`.

### Task A4: Migration 1 — identity schema (TDD)

**Files:**
- Create: `api/app/models/base.py`, modify `api/app/models/__init__.py`
- Create: `api/alembic/versions/0001_identity.py` (autogenerated then reviewed)
- Test: `api/tests/test_schema.py`

**Interfaces:**
- Produces (ORM classes importable from `app.models`): `Municipality(id, name, status, created_at)`, `Department(id, municipality_id, name, status, archive_expires_at, created_at)`, `User(id, email, password_hash, name, role, municipality_id, language, digest_enabled, status, token_version, last_login_at, created_at, departments: list[Department])`, `UserDepartment(user_id, department_id)`, `Invitation(id, email, role, municipality_id, department_ids, token_hash, invited_by, expires_at, used_at, created_at)`, `PasswordResetToken(id, user_id, token_hash, expires_at, used_at, created_at)`, `AuditLog(id, actor_id, action, entity_type, entity_id, before, after, created_at)`.

- [ ] Write failing test `api/tests/test_schema.py`:

```python
import uuid

from sqlalchemy import inspect


def test_identity_tables_exist(engine):
    tables = set(inspect(engine).get_table_names())
    assert {
        "municipalities", "departments", "users", "user_departments",
        "invitations", "password_reset_tokens", "audit_log",
    } <= tables


def test_user_department_roundtrip(db):
    from app.models import Department, Municipality, User

    muni = Municipality(name="Demo City")
    dept = Department(municipality=muni, name="Welfare")
    user = User(email="u@example.org", role="department_user", municipality=muni,
                departments=[dept])
    db.add_all([muni, dept, user])
    db.commit()
    loaded = db.get(User, user.id)
    assert loaded is not None and loaded.departments[0].name == "Welfare"
    assert loaded.status == "invited" and loaded.token_version == 0


def test_active_department_name_unique_per_municipality(db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.models import Department, Municipality

    muni = Municipality(name="Demo City")
    db.add(muni)
    db.add(Department(municipality=muni, name="Welfare"))
    db.commit()
    db.add(Department(municipality=muni, name="welfare"))
    with pytest.raises(IntegrityError):
        db.commit()
```

- [ ] Run → FAIL (models missing).
- [ ] Write models in `api/app/models/base.py` (all seven tables). Key requirements: UUID PKs `default=uuid.uuid4`; `server_default=func.now()` on `created_at`; CHECK constraints for role/status/language enums (`role IN ('system_admin','municipality_admin','department_user')` etc.); `users.email` unique via functional index `uq_users_email_lower` on `lower(email)`; departments partial unique index `uq_departments_active_name` on `(municipality_id, lower(name))` `WHERE status = 'active'`; `invitations.department_ids` JSONB default list; `audit_log.id` BigInteger identity; `before`/`after` JSONB nullable. Re-export all classes from `app/models/__init__.py`.
- [ ] Generate migration: `.venv\Scripts\python -m alembic revision --autogenerate -m "identity"` — then review/fix by hand: autogenerate misses the two functional/partial indexes (add `op.create_index` with `text()` expressions and `postgresql_where`) and must gain `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` as its first operation.
- [ ] Run full suite: `pytest -v` → PASS (health + schema).
- [ ] Verify downgrade: `alembic downgrade base && alembic upgrade head` against the dev DB.
- [ ] Commit: `feat(api): identity schema — users, municipalities, departments, invitations, tokens, audit_log`.

### Task A5: Web test tooling (vitest)

**Files:**
- Create: `web/lib/format.ts`, `web/lib/format.test.ts`, `web/vitest.config.ts`
- Modify: `web/package.json` (add `test` script + devDeps)

**Interfaces:**
- Produces: `formatBytes(n: number): string` (e.g. `formatBytes(1536) === "1.5 KB"`, used later by file cards); `npm test` runs vitest.

- [ ] `cd web && npm install` (scaffold deps), then `npm install -D vitest`.
- [ ] Write `web/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({ test: { include: ["**/*.test.{ts,tsx}"] } });
```

- [ ] Write failing test `web/lib/format.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { formatBytes } from "./format";

describe("formatBytes", () => {
  it("formats byte counts humanely", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(26214400)).toBe("25 MB");
  });
});
```

- [ ] Add `"test": "vitest run"` to package.json scripts; run `npm test` → FAIL.
- [ ] Implement `web/lib/format.ts`:

```ts
export function formatBytes(n: number): string {
  if (n === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), units.length - 1);
  const value = n / 1024 ** i;
  return `${Number(value.toFixed(1))} ${units[i]}`;
}
```

- [ ] `npm test` → PASS; `npx tsc --noEmit` → clean; `npm run lint` → clean.
- [ ] Commit: `feat(web): vitest harness + formatBytes util`.

### Task A6: CI workflow + secrets

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `.env` (secrets only — never committed; verify `.gitignore` covers it)

- [ ] Write `.github/workflows/ci.yml`:

```yaml
name: CI
on:
  push: { branches: [main] }
  pull_request:
jobs:
  web:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: web } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm, cache-dependency-path: web/package-lock.json }
      - run: npm ci
      - run: npx tsc --noEmit
      - run: npm run lint
      - run: npm test
  api:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: api } }
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env: { POSTGRES_USER: tah, POSTGRES_PASSWORD: tah, POSTGRES_DB: postgres }
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U tah" --health-interval 5s
          --health-timeout 5s --health-retries 10
    env:
      TEST_PG_URI: postgresql://tah:tah@localhost:5432/postgres
      DATABASE_URL: postgresql+psycopg://tah:tah@localhost:5432/postgres
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: pip install -r requirements.txt
      - run: ruff check .
      - run: mypy app
      - run: pytest -v
```

- [ ] Generate secrets locally (do not print): python one-liner writing `secrets.token_urlsafe(48)` into the `JWT_SECRET`, `NEXTAUTH_SECRET`, `CRON_SECRET` lines of `.env` in place. Confirm `.env` is gitignored (`git check-ignore .env` → path echoed).
- [ ] Run the full local gate exactly as CI would: api `ruff check . && mypy app && pytest -v`; web `npx tsc --noEmit && npm run lint && npm test`. All green.
- [ ] Commit: `chore: CI workflow (web + api jobs)`.

## Stage A exit criteria

- `python scripts/dev_db.py` idempotently starts local PG; `alembic upgrade head` clean; downgrade/upgrade cycle clean.
- `pytest -v` green on embedded PG (health + schema round-trip + unique-name guard).
- `npm test`, `npx tsc --noEmit`, `npm run lint` green.
- All work committed; working tree clean.
