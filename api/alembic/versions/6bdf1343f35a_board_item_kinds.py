"""board_item_kinds

A board post gains a kind: an ordinary post, an announcement, an event with a
date and place, or a question whose asker can mark the reply that answered it.

Every existing row becomes 'post', which is what they are.

Revision ID: 6bdf1343f35a
Revises: 50c7491c5c94
Create Date: 2026-08-12 17:06:35.982714

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6bdf1343f35a"
down_revision: Union[str, Sequence[str], None] = "50c7491c5c94"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "board_items",
        sa.Column("kind", sa.Text(), server_default="post", nullable=False),
    )
    op.add_column("board_items", sa.Column("event_at", sa.DateTime(timezone=True)))
    op.add_column(
        "board_items",
        sa.Column("event_has_time", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("board_items", sa.Column("event_location", sa.Text()))
    op.add_column("board_items", sa.Column("accepted_comment_id", sa.UUID()))

    op.create_check_constraint(
        "ck_board_items_kind",
        "board_items",
        "kind IN ('post','announcement','event','question')",
    )
    # An event with no date could not appear among what is coming up, which is
    # the only reason to mark one.
    op.create_check_constraint(
        "ck_board_items_event_at", "board_items", "kind != 'event' OR event_at IS NOT NULL"
    )
    op.create_check_constraint(
        "ck_board_items_accepted_question",
        "board_items",
        "accepted_comment_id IS NULL OR kind = 'question'",
    )

    # "what is coming up" is a scan of one kind ordered by date
    op.create_index("ix_board_items_event", "board_items", ["kind", "event_at"])
    # SET NULL rather than CASCADE: deleting the accepted reply must leave the
    # question standing, merely unanswered again.
    op.create_foreign_key(
        "fk_board_items_accepted_comment",
        "board_items",
        "board_comments",
        ["accepted_comment_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_board_items_accepted_comment", "board_items", type_="foreignkey")
    op.drop_index("ix_board_items_event", table_name="board_items")
    op.drop_constraint("ck_board_items_accepted_question", "board_items", type_="check")
    op.drop_constraint("ck_board_items_event_at", "board_items", type_="check")
    op.drop_constraint("ck_board_items_kind", "board_items", type_="check")
    op.drop_column("board_items", "accepted_comment_id")
    op.drop_column("board_items", "event_location")
    op.drop_column("board_items", "event_has_time")
    op.drop_column("board_items", "event_at")
    op.drop_column("board_items", "kind")
