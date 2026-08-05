import pytest


@pytest.mark.parametrize(
    "given,expected",
    [
        ("postgresql://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        # already explicit — left alone
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("", ""),
    ],
)
def test_database_url_normalised_for_psycopg3(monkeypatch, given, expected):
    """Railway and similar platforms provide bare postgres URLs; SQLAlchemy would
    otherwise try psycopg2, which this project does not install."""
    from app.core.config import Settings, get_settings

    monkeypatch.setattr("app.core.config.Settings", lambda: Settings(database_url=given))
    get_settings.cache_clear()
    try:
        assert get_settings().database_url == expected
    finally:
        get_settings.cache_clear()
