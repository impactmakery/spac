"""municipality_knowledge_base

Gives every municipality its own document library alongside the shared one.

Existing rows all become 'global', which is what they are: municipality_id has
always been stamped with the uploader's municipality even for shared documents,
so scope has to be its own column rather than something derived from it.

Revision ID: 50c7491c5c94
Revises: b3e91c7d5a08
Create Date: 2026-08-12 00:11:57.530072

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "50c7491c5c94"
down_revision: Union[str, Sequence[str], None] = "b3e91c7d5a08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "kb_documents",
        sa.Column("scope", sa.Text(), server_default="global", nullable=False),
    )
    op.create_check_constraint(
        "ck_kb_documents_scope", "kb_documents", "scope IN ('global','municipality')"
    )
    op.create_check_constraint(
        "ck_kb_documents_muni_scope",
        "kb_documents",
        "scope != 'municipality' OR municipality_id IS NOT NULL",
    )
    # the library listing always filters on these two together
    op.create_index(
        "ix_kb_documents_scope_municipality",
        "kb_documents",
        ["scope", "municipality_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_kb_documents_scope_municipality", table_name="kb_documents")
    op.drop_constraint("ck_kb_documents_muni_scope", "kb_documents", type_="check")
    op.drop_constraint("ck_kb_documents_scope", "kb_documents", type_="check")
    op.drop_column("kb_documents", "scope")
