"""add master resume skill dictionary

Revision ID: d4a1b2c3e4f5
Revises: c3d8a1e6b4f2
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d4a1b2c3e4f5"
down_revision = "c3d8a1e6b4f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "master_resumes",
        sa.Column("skill_dictionary", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("master_resumes", "skill_dictionary")
