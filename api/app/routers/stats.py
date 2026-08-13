import uuid
from datetime import date, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_municipality_admin, require_system_admin
from app.models import (
    DailyMetric,
    Department,
    Municipality,
    UnansweredQuestion,
    User,
)
from app.services.metrics import TZ
from app.services.stats_export import COPY, ExportInput, build_workbook

ALLOWED_RANGES = (7, 30, 90)


class Kpis(BaseModel):
    active_users: int
    chat_sessions: int
    chat_messages: int
    unanswered: int
    unanswered_pct: float
    board_items: int
    comments: int
    likes: int
    files_uploaded: int


class SeriesPoint(BaseModel):
    day: date
    active_users: int
    chat_messages: int


class BreakdownRow(BaseModel):
    id: str
    name: str
    kpis: Kpis


class StatsOut(BaseModel):
    range_days: int
    kpis: Kpis
    series: list[SeriesPoint]
    breakdown: list[BreakdownRow]


class UnansweredRow(BaseModel):
    question: str
    municipality_name: str | None
    created_at: date


class PlatformStatsOut(StatsOut):
    unanswered_questions: list[UnansweredRow]


def _kpis_from(rows) -> Kpis:
    totals = {
        "active_users": sum(r.active_users for r in rows),
        "chat_sessions": sum(r.chat_sessions for r in rows),
        "chat_messages": sum(r.chat_messages for r in rows),
        "unanswered": sum(r.unanswered for r in rows),
        "board_items": sum(r.board_items for r in rows),
        "comments": sum(r.comments for r in rows),
        "likes": sum(r.likes for r in rows),
        "files_uploaded": sum(r.files_uploaded for r in rows),
    }
    asked = totals["chat_messages"]
    pct = round(100 * totals["unanswered"] / asked, 1) if asked else 0.0
    return Kpis(**totals, unanswered_pct=pct)


def _window(range_days: int) -> tuple[date, date]:
    if range_days not in ALLOWED_RANGES:
        raise HTTPException(status_code=422, detail="invalid_range")
    today = __import__("datetime").datetime.now(TZ).date()
    return today - timedelta(days=range_days - 1), today


router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/municipality", response_model=StatsOut)
def municipality_stats(
    range_days: int = 30,
    municipality_id: str | None = None,
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> StatsOut:
    start, end = _window(range_days)
    if actor.role == "municipality_admin":
        target = actor.municipality_id
    else:
        target = uuid.UUID(municipality_id) if municipality_id else None
        if target is None:
            raise HTTPException(status_code=422, detail="municipality_required")
    if target is None:
        raise HTTPException(status_code=404, detail="not_found")

    base = select(DailyMetric).where(
        DailyMetric.day >= start,
        DailyMetric.day <= end,
        DailyMetric.municipality_id == target,
    )
    muni_rows = list(db.scalars(base.where(DailyMetric.department_id.is_(None))))
    series = [
        SeriesPoint(
            day=r.day, active_users=r.active_users, chat_messages=r.chat_messages
        )
        for r in sorted(muni_rows, key=lambda r: r.day)
    ]

    breakdown = []
    departments = db.scalars(
        select(Department).where(
            Department.municipality_id == target, Department.status == "active"
        )
    ).all()
    for department in departments:
        rows = list(db.scalars(base.where(DailyMetric.department_id == department.id)))
        breakdown.append(
            BreakdownRow(
                id=str(department.id), name=department.name, kpis=_kpis_from(rows)
            )
        )

    return StatsOut(
        range_days=range_days,
        kpis=_kpis_from(muni_rows),
        series=series,
        breakdown=breakdown,
    )


@router.get("/platform", response_model=PlatformStatsOut)
def platform_stats(
    range_days: int = 30,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> PlatformStatsOut:
    start, end = _window(range_days)
    window = (DailyMetric.day >= start, DailyMetric.day <= end)

    platform_rows = list(
        db.scalars(
            select(DailyMetric).where(
                *window,
                DailyMetric.municipality_id.is_(None),
                DailyMetric.department_id.is_(None),
            )
        )
    )
    series = [
        SeriesPoint(
            day=r.day, active_users=r.active_users, chat_messages=r.chat_messages
        )
        for r in sorted(platform_rows, key=lambda r: r.day)
    ]

    breakdown = []
    for municipality in db.scalars(select(Municipality).order_by(Municipality.name)):
        rows = list(
            db.scalars(
                select(DailyMetric).where(
                    *window,
                    DailyMetric.municipality_id == municipality.id,
                    DailyMetric.department_id.is_(None),
                )
            )
        )
        breakdown.append(
            BreakdownRow(
                id=str(municipality.id), name=municipality.name, kpis=_kpis_from(rows)
            )
        )

    unanswered = db.execute(
        select(
            UnansweredQuestion.question,
            Municipality.name,
            func.max(UnansweredQuestion.created_at).label("last_asked"),
        )
        .join(
            Municipality,
            Municipality.id == UnansweredQuestion.municipality_id,
            isouter=True,
        )
        .group_by(UnansweredQuestion.question, Municipality.name)
        .order_by(desc("last_asked"))
        .limit(50)
    ).all()

    return PlatformStatsOut(
        range_days=range_days,
        kpis=_kpis_from(platform_rows),
        series=series,
        breakdown=breakdown,
        unanswered_questions=[
            UnansweredRow(
                question=q, municipality_name=name, created_at=last_asked.date()
            )
            for q, name, last_asked in unanswered
        ],
    )


def _xlsx_response(data: ExportInput, filename: str) -> Response:
    return Response(
        content=build_workbook(data),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            # filename* so a Hebrew name survives the trip; filename= as the
            # fallback for anything that does not read RFC 5987.
            "Content-Disposition": (
                f'attachment; filename="{filename}"; '
                f"filename*=UTF-8''{quote(filename)}"
            )
        },
    )


@router.get("/platform.xlsx")
def platform_stats_xlsx(
    range_days: int = 30,
    lang: str = "he",
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> Response:
    """The same figures as /platform, as a workbook with live Excel charts.

    Built here rather than in the browser because the charts are real ones —
    each points at a range on a sheet, so a number changed in Excel moves the
    chart with it.
    """
    stats = platform_stats(range_days=range_days, actor=actor, db=db)
    return _xlsx_response(
        ExportInput(
            lang=lang,
            range_days=range_days,
            scope="platform",
            title=COPY.get(lang, COPY["he"])["by_group"],
            kpis=stats.kpis,
            series=stats.series,
            breakdown=stats.breakdown,
            unanswered=stats.unanswered_questions,
        ),
        f"usage-platform-{range_days}d.xlsx",
    )


@router.get("/municipality.xlsx")
def municipality_stats_xlsx(
    range_days: int = 30,
    municipality_id: str | None = None,
    lang: str = "he",
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> Response:
    stats = municipality_stats(
        range_days=range_days, municipality_id=municipality_id, actor=actor, db=db
    )
    return _xlsx_response(
        ExportInput(
            lang=lang,
            range_days=range_days,
            scope="municipality",
            title=COPY.get(lang, COPY["he"])["by_group_dept"],
            kpis=stats.kpis,
            series=stats.series,
            breakdown=stats.breakdown,
            unanswered=None,
        ),
        f"usage-municipality-{range_days}d.xlsx",
    )
