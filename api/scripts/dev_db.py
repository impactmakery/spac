"""Start (or reuse) the local dev Postgres and sync DATABASE_URL in .env.

Embedded PostgreSQL 16 + pgvector via pgserver — no Docker required.
The server picks a free port on each cold start, so this script rewrites
the DATABASE_URL line in the repo-root .env to match.

Usage:
    python scripts/dev_db.py         # start (idempotent) and sync .env
    python scripts/dev_db.py stop    # stop the server
"""

import re
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
ROOT = API_DIR.parent
PGDATA = API_DIR / "var" / "pgdata"


def main() -> None:
    import pgserver

    PGDATA.parent.mkdir(parents=True, exist_ok=True)

    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        pgserver.get_server(PGDATA, cleanup_mode=None).cleanup()
        print("stopped")
        return

    server = pgserver.get_server(PGDATA, cleanup_mode=None)
    if "tah" not in server.psql("SELECT datname FROM pg_database"):
        server.psql("CREATE DATABASE tah")

    uri = server.get_uri("tah")
    import psycopg

    with psycopg.connect(uri, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

    url = uri.replace("postgresql://", "postgresql+psycopg://")
    env_path = ROOT / ".env"
    text = env_path.read_text(encoding="utf-8")
    text = re.sub(r"^DATABASE_URL=.*$", f"DATABASE_URL={url}", text, flags=re.M)
    env_path.write_text(text, encoding="utf-8")
    print(url)


if __name__ == "__main__":
    main()
