import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# Per-session template name: two pytest sessions sharing one server would
# otherwise drop and recreate each other's template mid-run, failing random
# tests with confusing psycopg errors.
TEMPLATE = f"tah_test_template_{os.getpid()}"


@pytest.fixture(autouse=True, scope="session")
def _hermetic_providers():
    """Keep the suite offline and deterministic.

    A developer's .env holds real provider keys for running the app; tests must
    not spend money or depend on a network, so those are ignored here. Keys
    exported in the shell ARE honoured — that is how CI and the opt-in live RAG
    eval ask for the real providers.

    R2 belongs in this list too: with real bucket credentials present,
    get_storage() hands back the R2 provider and every upload test writes to —
    and reads from — the production bucket over the network.
    """
    from app.core.config import get_settings

    settings = get_settings()
    saved: dict[str, str] = {}
    for field in (
        "openai_api_key",
        "llm_api_key",
        "embedding_api_key",
        "r2_account_id",
        "r2_access_key_id",
        "r2_secret_access_key",
    ):
        if not os.environ.get(field.upper()):  # came from .env, not the shell
            saved[field] = getattr(settings, field)
            setattr(settings, field, "")
            # Blanking the live object is not enough: get_settings() is cached,
            # and any test that clears that cache (test_config does) rebuilds
            # Settings straight from .env, handing every later test the real
            # keys. An empty env var outranks the .env file, so a rebuilt
            # Settings stays hermetic too.
            os.environ[field.upper()] = ""
    yield
    for field, value in saved.items():
        setattr(settings, field, value)
        os.environ.pop(field.upper(), None)


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """Module-level limiters share state across tests (same 'testclient' IP)."""
    from app.core.ratelimit import forgot_limiter, login_limiter

    login_limiter.reset("testclient")
    forgot_limiter.reset("testclient")
    yield


@pytest.fixture(scope="session")
def pg_uri() -> str:
    """Plain postgres URI to the server's maintenance DB (no +psycopg)."""
    if os.environ.get("TEST_PG_URI"):  # CI: service container
        return os.environ["TEST_PG_URI"]

    import pgserver

    pgdata = Path(__file__).resolve().parents[1] / "var" / "pgdata_test"
    pgdata.parent.mkdir(parents=True, exist_ok=True)
    server = pgserver.get_server(pgdata, cleanup_mode=None)
    return server.get_uri()


@pytest.fixture(scope="session")
def template_db(pg_uri: str) -> Iterator[str]:
    from alembic.config import Config

    from alembic import command

    with psycopg.connect(pg_uri, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{TEMPLATE}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{TEMPLATE}"')
    tmpl_uri = pg_uri.rsplit("/", 1)[0] + f"/{TEMPLATE}"
    with psycopg.connect(tmpl_uri, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option(
        "sqlalchemy.url", tmpl_uri.replace("postgresql://", "postgresql+psycopg://")
    )
    command.upgrade(cfg, "head")
    yield tmpl_uri

    with psycopg.connect(pg_uri, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{TEMPLATE}" WITH (FORCE)')


@pytest.fixture()
def db_url(pg_uri: str, template_db: str) -> Iterator[str]:
    name = f"tah_t_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(pg_uri, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}" TEMPLATE "{TEMPLATE}"')
    yield pg_uri.rsplit("/", 1)[0] + f"/{name}"
    with psycopg.connect(pg_uri, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


@pytest.fixture()
def engine(db_url: str) -> Iterator[Engine]:
    eng = create_engine(db_url.replace("postgresql://", "postgresql+psycopg://"))
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine: Engine) -> Iterator[Session]:
    with sessionmaker(bind=engine)() as session:
        yield session


@pytest.fixture()
def client(engine: Engine) -> Iterator[TestClient]:
    from app.core import db as db_module
    from app.core.db import get_db
    from app.main import create_app

    app = create_app()

    def override() -> Iterator[Session]:
        with sessionmaker(bind=engine)() as session:
            yield session

    app.dependency_overrides[get_db] = override

    # A dependency override does not reach the code that opens its own session
    # — the unhandled-error handler, which cannot use the request's session
    # because that one is inside a failed transaction. Left alone it would
    # write into whatever DATABASE_URL names, which in a test run is a
    # developer's own database.
    previous = db_module._session_factory
    db_module._session_factory = sessionmaker(bind=engine)
    try:
        with TestClient(app) as c:
            yield c
    finally:
        db_module._session_factory = previous

