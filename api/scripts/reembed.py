"""Re-embed every indexed source — run after changing EMBEDDING_MODEL.

Vectors from different models are not comparable, so a model switch must
rebuild every chunk. Queues one ingestion job per source and lets the worker
do the work; safe to run while the app is live.

Usage: python scripts/reembed.py [--run]
       --run also processes the queue here instead of waiting for the worker.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models import (  # noqa: E402
    BoardItem,
    Department,
    DepartmentFile,
    DepartmentPost,
    KbDocument,
)
from app.services.ingestion import enqueue, run_pending_jobs  # noqa: E402


def requeue(db: Session) -> int:
    """Queue every indexed source for re-embedding. Caller commits.

    Separated from main so a test can prove the one rule that matters here:
    each source is re-queued at its own visibility. A constant would work
    perfectly and silently republish every municipality's library to all of
    them the next time the embedding model changed.
    """
    queued = 0
    for doc in db.scalars(select(KbDocument)):
        enqueue(
            db, source_type="kb", source_id=doc.id,
            visibility=doc.scope,
            municipality_id=(
                doc.municipality_id if doc.scope == "municipality" else None
            ),
            storage_key=doc.storage_key,
            ext=doc.filename.rsplit(".", 1)[-1].lower(),
            title=doc.title,
        )
        doc.status = "pending"
        queued += 1

    for item in db.scalars(select(BoardItem)):
        enqueue(
            db, source_type="board", source_id=item.id,
            visibility="global" if item.scope == "global" else "municipality",
            storage_key=item.storage_key,
            ext=item.filename.rsplit(".", 1)[-1].lower() if item.filename else None,
            text_content=item.description or "",
            title=item.title,
            municipality_id=item.municipality_id,
        )
        item.indexing_status = "pending"
        queued += 1

    for file in db.scalars(select(DepartmentFile)):
        department = db.get(Department, file.department_id)
        enqueue(
            db, source_type="department", source_id=file.id,
            visibility="department", storage_key=file.storage_key,
            ext=file.filename.rsplit(".", 1)[-1].lower(),
            title=file.filename,
            municipality_id=department.municipality_id if department else None,
            department_id=file.department_id,
        )
        file.status = "pending"
        queued += 1

    for post in db.scalars(select(DepartmentPost)):
        department = db.get(Department, post.department_id)
        enqueue(
            db, source_type="department", source_id=post.id,
            visibility="department", text_content=post.body,
            municipality_id=department.municipality_id if department else None,
            department_id=post.department_id,
        )
        queued += 1
    return queued


def main() -> None:
    settings = get_settings()
    print(f"embedding model: {settings.embedding_model}")
    engine = create_engine(settings.database_url)

    with sessionmaker(bind=engine)() as db:
        queued = requeue(db)
        db.commit()
        print(f"queued {queued} source(s) for re-embedding")

        if "--run" in sys.argv:
            processed = 0
            while True:
                batch = run_pending_jobs(db, limit=20)
                if not batch:
                    break
                processed += batch
                print(f"  processed {processed}/{queued}", flush=True)
            print(f"done: {processed} job(s) processed")
        else:
            print("the ingestion worker will process these; or re-run with --run")


if __name__ == "__main__":
    main()
