from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_session_factory: sessionmaker[Session] | None = None


def get_db() -> Iterator[Session]:
    global _session_factory
    if _session_factory is None:
        engine = create_engine(get_settings().database_url, pool_pre_ping=True)
        _session_factory = sessionmaker(bind=engine)
    with _session_factory() as session:
        yield session
