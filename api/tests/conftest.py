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

TEMPLATE = "tah_test_template"


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
def template_db(pg_uri: str) -> str:
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
    return tmpl_uri


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
    from app.core.db import get_db
    from app.main import create_app

    app = create_app()

    def override() -> Iterator[Session]:
        with sessionmaker(bind=engine)() as session:
            yield session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
