"""board_search_includes_prompt

Prompt text was searchable by the assistant but not by the board's own search,
so a post whose substance is a shared prompt could only be found by its title.

The search column is generated, and Postgres cannot redefine a generated
expression in place — it is dropped and recreated, which recomputes every row.

Revision ID: a1c7e4b93f20
Revises: 6d707bb04494
Create Date: 2026-08-09

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1c7e4b93f20"
down_revision: str | Sequence[str] | None = "6d707bb04494"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WITH_PROMPT = (
    "to_tsvector('simple', coalesce(title,'') || ' ' || "
    "coalesce(description,'') || ' ' || coalesce(prompt_text,''))"
)
WITHOUT_PROMPT = (
    "to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(description,''))"
)


def _rebuild(expression: str) -> None:
    op.drop_index("ix_board_items_search", table_name="board_items", postgresql_using="gin")
    op.drop_column("board_items", "search")
    op.add_column(
        "board_items",
        sa.Column(
            "search",
            postgresql.TSVECTOR(),
            sa.Computed(expression, persisted=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_board_items_search", "board_items", ["search"], postgresql_using="gin"
    )


def upgrade() -> None:
    _rebuild(WITH_PROMPT)


def downgrade() -> None:
    _rebuild(WITHOUT_PROMPT)
