"""index_board_comments

Comments carry corrections and clarifications — "that form was replaced last
year" — and the assistant could not see any of it. Indexing them needs a fourth
source type alongside kb, board and department.

Revision ID: b3e91c7d5a08
Revises: 0c5d0621aa40
Create Date: 2026-08-09

"""
from collections.abc import Sequence

from alembic import op

revision: str = "b3e91c7d5a08"
down_revision: str | Sequence[str] | None = "0c5d0621aa40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_chunks_source_type", "chunks", type_="check")
    op.create_check_constraint(
        "ck_chunks_source_type",
        "chunks",
        "source_type IN ('kb','board','department','comment')",
    )


def downgrade() -> None:
    # Comment chunks would violate the narrower constraint, so they go first.
    op.execute("DELETE FROM chunks WHERE source_type = 'comment'")
    op.execute("DELETE FROM ingestion_jobs WHERE source_type = 'comment'")
    op.drop_constraint("ck_chunks_source_type", "chunks", type_="check")
    op.create_check_constraint(
        "ck_chunks_source_type",
        "chunks",
        "source_type IN ('kb','board','department')",
    )
