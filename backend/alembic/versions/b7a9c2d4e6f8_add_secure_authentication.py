"""add secure authentication and per-user ownership

Revision ID: b7a9c2d4e6f8
Revises: d4a1b2c3e4f5
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "b7a9c2d4e6f8"
down_revision = "d4a1b2c3e4f5"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("users", sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), primary_key=True), sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False, unique=True), sa.Column("password_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False), sa.Column("email_verified_at", sa.DateTime(timezone=True)), sa.Column("failed_login_count", sa.Integer(), nullable=False), sa.Column("locked_until", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table("auth_tokens", sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), primary_key=True), sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), sa.ForeignKey("users.id"), nullable=False), sa.Column("token_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False, unique=True), sa.Column("purpose", sqlmodel.sql.sqltypes.AutoString(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("used_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_auth_tokens_user_id", "auth_tokens", ["user_id"]); op.create_index("ix_auth_tokens_token_hash", "auth_tokens", ["token_hash"]); op.create_index("ix_auth_tokens_purpose", "auth_tokens", ["purpose"])
    op.create_table("user_sessions", sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), primary_key=True), sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), sa.ForeignKey("users.id"), nullable=False), sa.Column("token_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"]); op.create_index("ix_user_sessions_token_hash", "user_sessions", ["token_hash"])
    # Existing unowned records cannot safely be assigned. They remain inaccessible.
    op.add_column("tailored_resumes", sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True)); op.create_index("ix_tailored_resumes_user_id", "tailored_resumes", ["user_id"])
    op.add_column("master_resumes", sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True)); op.create_index("ix_master_resumes_user_id", "master_resumes", ["user_id"])

def downgrade():
    op.drop_index("ix_master_resumes_user_id", table_name="master_resumes"); op.drop_column("master_resumes", "user_id")
    op.drop_index("ix_tailored_resumes_user_id", table_name="tailored_resumes"); op.drop_column("tailored_resumes", "user_id")
    op.drop_table("user_sessions"); op.drop_table("auth_tokens"); op.drop_table("users")
