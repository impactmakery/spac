"""Nightly rollup into daily_metrics. Dashboards read only from these rows.

Idempotent per day: a re-run deletes and rebuilds that day's rows, so a retried
cron never double-counts.
"""

import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, union
from sqlalchemy.orm import Session

from app.models import (
    BoardComment,
    BoardItem,
    BoardLike,
    Conversation,
    DailyMetric,
    DepartmentFile,
    KbDocument,
    Message,
    UnansweredQuestion,
    User,
    UserDepartment,
    UserLogin,
)

TZ = ZoneInfo("Asia/Jerusalem")


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """Local-day window: metrics are reported in the municipalities' timezone."""
    start = datetime.combine(day, time.min, tzinfo=TZ)
    return start, start + timedelta(days=1)


def _count(db: Session, stmt) -> int:
    return db.scalar(stmt) or 0


def rollup_day(db: Session, day: date) -> dict[str, int]:
    """Rebuild every metrics row for `day`. Returns row counts written."""
    start, end = day_bounds(day)

    db.execute(delete(DailyMetric).where(DailyMetric.day == day))

    municipality_ids = [
        m for m in db.scalars(select(User.municipality_id).distinct()) if m is not None
    ]

    def metrics_for(
        municipality_id: uuid.UUID | None, department_id: uuid.UUID | None
    ) -> DailyMetric:
        # user scope for this row
        user_q = select(User.id)
        if department_id is not None:
            user_q = user_q.join(
                UserDepartment, UserDepartment.user_id == User.id
            ).where(UserDepartment.department_id == department_id)
        elif municipality_id is not None:
            user_q = user_q.where(User.municipality_id == municipality_id)
        user_ids = list(db.scalars(user_q))

        # Who did something, not who signed in.
        #
        # Sessions last thirty days, so counting logins meant somebody who
        # signed in once and then used the assistant every day for a month
        # appeared on exactly one of those days. The undercount grew with
        # loyalty, which is backwards for a usage figure. Every source below
        # carries a user id already; a person counts once however many of
        # these they did.
        def _actors(column, model, *conditions):
            q = select(column.label("user_id")).where(
                model.created_at >= start, model.created_at < end, *conditions
            )
            return q

        active_q = union(
            _actors(UserLogin.user_id, UserLogin),
            _actors(Conversation.user_id, Conversation),
            _actors(BoardItem.author_id, BoardItem),
            _actors(BoardComment.author_id, BoardComment),
        ).subquery()
        login_q = select(func.count(func.distinct(active_q.c.user_id))).select_from(
            active_q
        )
        convo_q = select(func.count(Conversation.id)).where(
            Conversation.created_at >= start, Conversation.created_at < end
        )
        msg_q = (
            select(func.count(Message.id))
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Message.created_at >= start,
                Message.created_at < end,
                Message.role == "user",
            )
        )
        unanswered_q = select(func.count(UnansweredQuestion.id)).where(
            UnansweredQuestion.created_at >= start, UnansweredQuestion.created_at < end
        )
        items_q = select(func.count(BoardItem.id)).where(
            BoardItem.created_at >= start, BoardItem.created_at < end
        )
        comments_q = select(func.count(BoardComment.id)).where(
            BoardComment.created_at >= start, BoardComment.created_at < end
        )
        likes_q = select(func.count()).select_from(BoardLike).where(
            BoardLike.created_at >= start, BoardLike.created_at < end
        )
        kb_q = select(func.count(KbDocument.id)).where(
            KbDocument.created_at >= start, KbDocument.created_at < end
        )
        dept_files_q = select(func.count(DepartmentFile.id)).where(
            DepartmentFile.created_at >= start, DepartmentFile.created_at < end
        )

        if municipality_id is not None or department_id is not None:
            # filter the union, not the login table it no longer selects from
            login_q = login_q.where(active_q.c.user_id.in_(user_ids))
            convo_q = convo_q.where(Conversation.user_id.in_(user_ids))
            msg_q = msg_q.where(Conversation.user_id.in_(user_ids))
            unanswered_q = unanswered_q.where(UnansweredQuestion.user_id.in_(user_ids))
            items_q = items_q.where(BoardItem.author_id.in_(user_ids))
            comments_q = comments_q.where(BoardComment.author_id.in_(user_ids))
            likes_q = likes_q.where(BoardLike.user_id.in_(user_ids))
            kb_q = kb_q.where(KbDocument.uploader_id.in_(user_ids))
            dept_files_q = dept_files_q.where(DepartmentFile.uploader_id.in_(user_ids))
        if department_id is not None:
            dept_files_q = dept_files_q.where(
                DepartmentFile.department_id == department_id
            )

        return DailyMetric(
            day=day,
            municipality_id=municipality_id,
            department_id=department_id,
            active_users=_count(db, login_q),
            chat_sessions=_count(db, convo_q),
            chat_messages=_count(db, msg_q),
            unanswered=_count(db, unanswered_q),
            board_items=_count(db, items_q),
            comments=_count(db, comments_q),
            likes=_count(db, likes_q),
            files_uploaded=_count(db, kb_q) + _count(db, dept_files_q),
        )

    rows = [metrics_for(None, None)]  # platform total
    for municipality_id in municipality_ids:
        rows.append(metrics_for(municipality_id, None))
        from app.models import Department

        department_ids = db.scalars(
            select(Department.id).where(Department.municipality_id == municipality_id)
        )
        for department_id in department_ids:
            rows.append(metrics_for(municipality_id, department_id))

    db.add_all(rows)
    db.commit()
    return {"rows": len(rows), "municipalities": len(municipality_ids)}
