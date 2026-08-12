"""A worker that dies must not take its claimed jobs with it.

Jobs are claimed in a batch and marked 'running' before any of them is worked
on. If the process is killed in the middle — out of memory on a large scan, a
deploy, a restart — those rows stay 'running', and the claim query only ever
looks at 'queued'. Nothing retries them, the document shows "processing"
forever, and the only clue is a count that never reaches the total.

This happened in production: 21 documents stranded for nine hours after the
worker was killed OCR'ing scanned PDFs.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest


@pytest.fixture()
def doc(db):
    from app.core.security import hash_password
    from app.models import KbDocument, User

    user = User(email="r@x.org", role="system_admin", status="active",
                password_hash=hash_password("reclaim-pw-1"), name="Root")
    db.add(user)
    db.flush()
    d = KbDocument(title="Big scan", filename="scan.pdf", storage_key="k",
                   size_bytes=1, content_type="application/pdf",
                   uploader_id=user.id, status="processing", scope="global")
    db.add(d)
    db.commit()
    return d


def _stranded_job(db, doc, *, age_seconds: int, attempts: int = 0):
    """A job claimed by a worker that never came back."""
    from app.models import IngestionJob

    job = IngestionJob(
        source_type="kb",
        source_id=doc.id,
        payload={"storage_key": "k", "ext": "pdf", "title": doc.title,
                 "visibility": "global", "municipality_id": None, "department_id": None},
        status="running",
        attempts=attempts,
    )
    db.add(job)
    db.commit()
    # onupdate would stamp it now, so age it with SQL the ORM will not overwrite
    from sqlalchemy import text

    db.execute(
        text("UPDATE ingestion_jobs SET updated_at = :t WHERE id = :i"),
        {"t": datetime.now(UTC) - timedelta(seconds=age_seconds), "i": job.id},
    )
    db.commit()
    return job


def test_a_job_abandoned_by_a_dead_worker_goes_back_to_the_queue(db, doc):
    from app.models import IngestionJob
    from app.services.ingestion import LEASE_SECONDS, reclaim_stalled_jobs

    job = _stranded_job(db, doc, age_seconds=LEASE_SECONDS + 60)

    assert reclaim_stalled_jobs(db) == 1
    db.expire_all()
    assert db.get(IngestionJob, job.id).status == "queued"
    assert db.get(IngestionJob, job.id).attempts == 1
    # and the document stops claiming to be mid-processing
    from app.models import KbDocument

    assert db.get(KbDocument, doc.id).status == "pending"


def test_a_job_still_within_its_lease_is_left_alone(db, doc):
    """A healthy worker must not have its own work taken away mid-run."""
    from app.models import IngestionJob
    from app.services.ingestion import LEASE_SECONDS, reclaim_stalled_jobs

    job = _stranded_job(db, doc, age_seconds=LEASE_SECONDS - 60)

    assert reclaim_stalled_jobs(db) == 0
    db.expire_all()
    assert db.get(IngestionJob, job.id).status == "running"


def test_a_document_that_keeps_killing_the_worker_eventually_gives_up(db, doc):
    """Otherwise one poisonous file cycles forever, taking the queue with it."""
    from app.models import IngestionJob, KbDocument
    from app.services.ingestion import LEASE_SECONDS, MAX_ATTEMPTS, reclaim_stalled_jobs

    job = _stranded_job(db, doc, age_seconds=LEASE_SECONDS + 60,
                        attempts=MAX_ATTEMPTS - 1)

    assert reclaim_stalled_jobs(db) == 1
    db.expire_all()
    assert db.get(IngestionJob, job.id).status == "failed"
    assert db.get(KbDocument, doc.id).status == "not_indexable"


def test_running_jobs_are_reclaimed_by_the_ordinary_worker_cycle(db, doc):
    """The recovery has to happen on its own, not only when someone runs a script."""
    from app.models import IngestionJob
    from app.services.ingestion import LEASE_SECONDS, run_pending_jobs

    job = _stranded_job(db, doc, age_seconds=LEASE_SECONDS + 60)
    run_pending_jobs(db, limit=5)

    db.expire_all()
    reloaded = db.get(IngestionJob, job.id)
    # picked back up: either retried and failed on the missing file, or queued
    assert reloaded.status != "running"
    assert reloaded.attempts >= 1


def test_an_unrelated_queued_job_is_untouched(db, doc):
    from app.models import IngestionJob
    from app.services.ingestion import reclaim_stalled_jobs

    job = IngestionJob(source_type="kb", source_id=uuid.uuid4(), payload={},
                       status="queued")
    db.add(job)
    db.commit()

    assert reclaim_stalled_jobs(db) == 0
    db.expire_all()
    assert db.get(IngestionJob, job.id).attempts == 0


# --- OCR memory ------------------------------------------------------------


class _FakePage:
    def __init__(self, width: float, height: float) -> None:
        self._size = (width, height)

    def get_size(self):
        return self._size


@pytest.mark.parametrize(
    ("name", "width_pt", "height_pt"),
    [("A4", 595, 842), ("A3", 842, 1191)],
)
def test_ordinary_pages_render_at_full_resolution(name, width_pt, height_pt):
    """Scaling down costs accuracy, so it must only happen when it has to."""
    from app.rag.extract import OCR_DPI, _render_scale

    assert _render_scale(_FakePage(width_pt, height_pt)) == pytest.approx(OCR_DPI / 72)


def test_a_huge_page_is_scaled_down_to_a_bitmap_that_fits_in_memory():
    """An A0 plan at 200 dpi is a 182 MB bitmap, and the worker has a gigabyte.

    Hebrew municipal archives are full of scanned plans; one of them taking the
    worker out of memory stranded 21 documents in production.
    """
    from app.rag.extract import OCR_MAX_PIXELS, _render_scale

    a0 = _FakePage(3370, 2384)  # A0 in points
    scale = _render_scale(a0)
    pixels = (3370 * scale) * (2384 * scale)
    assert pixels <= OCR_MAX_PIXELS * 1.01
    assert pixels > OCR_MAX_PIXELS * 0.9, "scaled down further than necessary"


def test_a_page_that_will_not_report_its_size_still_renders():
    """OCR is best-effort; an odd page must not stop the document."""
    from app.rag.extract import OCR_DPI, _render_scale

    class Broken:
        def get_size(self):
            raise RuntimeError("no size")

    assert _render_scale(Broken()) == pytest.approx(OCR_DPI / 72)


# --- graceful shutdown -----------------------------------------------------
#
# A deploy is an ordinary event, and Railway sends SIGTERM before replacing the
# container. Dying on the spot left a whole claimed batch to sit out the lease:
# that, not a crash, is what stranded 21 documents here for nine hours.


def test_shutdown_hands_back_the_jobs_it_has_not_started(db, doc):
    from app.models import IngestionJob
    from app.services.ingestion import enqueue, run_pending_jobs

    for _ in range(3):
        enqueue(db, source_type="kb", source_id=doc.id, visibility="global",
                storage_key="missing", ext="pdf", title=doc.title)
    db.commit()

    # asked to stop before any job is started
    processed = run_pending_jobs(db, limit=3, should_stop=lambda: True)

    assert processed == 0
    db.expire_all()
    statuses = {j.status for j in db.query(IngestionJob).all()}
    assert statuses == {"queued"}
    # handed back, not retried: they were never attempted
    assert all(j.attempts == 0 for j in db.query(IngestionJob).all())


def test_shutdown_leaves_nothing_claimed(db, doc):
    """Whatever state a stopping worker leaves, it must not be 'running'."""
    from app.models import IngestionJob
    from app.services.ingestion import enqueue, run_pending_jobs

    for _ in range(2):
        enqueue(db, source_type="kb", source_id=doc.id, visibility="global",
                storage_key="missing", ext="pdf", title=doc.title)
    db.commit()

    calls = {"n": 0}

    def stop_after_first() -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    run_pending_jobs(db, limit=2, should_stop=stop_after_first)
    db.expire_all()
    assert not [j for j in db.query(IngestionJob).all() if j.status == "running"]
