"""store timestamps with time zone"""

revision = "c3d8a1e6b4f2"
down_revision = "8f567b9e2697"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.alter_column("tailored_resumes", "created_at", existing_type=sa.DateTime(), type_=sa.DateTime(timezone=True), existing_nullable=False, postgresql_using="created_at AT TIME ZONE 'UTC'")
    op.alter_column("master_resumes", "created_at", existing_type=sa.DateTime(), type_=sa.DateTime(timezone=True), existing_nullable=False, postgresql_using="created_at AT TIME ZONE 'UTC'")
    op.alter_column("master_resumes", "updated_at", existing_type=sa.DateTime(), type_=sa.DateTime(timezone=True), existing_nullable=False, postgresql_using="updated_at AT TIME ZONE 'UTC'")


def downgrade() -> None:
    op.alter_column("master_resumes", "updated_at", existing_type=sa.DateTime(timezone=True), type_=sa.DateTime(), existing_nullable=False, postgresql_using="updated_at AT TIME ZONE 'UTC'")
    op.alter_column("master_resumes", "created_at", existing_type=sa.DateTime(timezone=True), type_=sa.DateTime(), existing_nullable=False, postgresql_using="created_at AT TIME ZONE 'UTC'")
    op.alter_column("tailored_resumes", "created_at", existing_type=sa.DateTime(timezone=True), type_=sa.DateTime(), existing_nullable=False, postgresql_using="created_at AT TIME ZONE 'UTC'")
