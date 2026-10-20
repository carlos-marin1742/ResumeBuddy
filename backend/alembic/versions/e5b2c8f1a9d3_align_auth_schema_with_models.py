"""align auth schema with models and cascade on user delete

Revision ID: e5b2c8f1a9d3
Revises: b7a9c2d4e6f8

Makes user_id required on both resume tables, adds foreign keys to users.id
with ON DELETE CASCADE (replacing the cascade-less keys on auth_tokens and
user_sessions), and replaces each unique-constraint-plus-plain-index pair
with the single unique index the models declare.

Upgrade deletes resume rows with a NULL user_id: b7a9c2d4e6f8 left them
unowned and inaccessible, and they cannot be assigned to anyone. The delete
is not reversible; downgrade restores the schema, not those rows.
"""

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = "e5b2c8f1a9d3"
down_revision = "b7a9c2d4e6f8"
branch_labels = None
depends_on = None

# (table, column, constraint b7a9c2d4e6f8 created, index name the models use)
UNIQUE_COLUMNS = [
    ("users", "email", "users_email_key", "ix_users_email"),
    ("auth_tokens", "token_hash", "auth_tokens_token_hash_key", "ix_auth_tokens_token_hash"),
    ("user_sessions", "token_hash", "user_sessions_token_hash_key", "ix_user_sessions_token_hash"),
]
RESUME_TABLES = ["master_resumes", "tailored_resumes"]
# Tables whose user_id foreign key b7a9c2d4e6f8 created without a name or cascade.
KEYED_TABLES = ["auth_tokens", "user_sessions"]


def _fk_name(table: str) -> str:
    return f"fk_{table}_user_id_users"


def upgrade() -> None:
    for table in RESUME_TABLES:
        op.execute(sa.text(f"DELETE FROM {table} WHERE user_id IS NULL"))
        op.alter_column(
            table,
            "user_id",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        )
        op.create_foreign_key(
            _fk_name(table), table, "users", ["user_id"], ["id"], ondelete="CASCADE"
        )

    for table in KEYED_TABLES:
        op.drop_constraint(f"{table}_user_id_fkey", table, type_="foreignkey")
        op.create_foreign_key(
            _fk_name(table), table, "users", ["user_id"], ["id"], ondelete="CASCADE"
        )

    for table, column, constraint, index in UNIQUE_COLUMNS:
        op.drop_index(index, table_name=table)
        op.drop_constraint(constraint, table, type_="unique")
        op.create_index(index, table, [column], unique=True)


def downgrade() -> None:
    for table, column, constraint, index in reversed(UNIQUE_COLUMNS):
        op.drop_index(index, table_name=table)
        op.create_unique_constraint(constraint, table, [column])
        op.create_index(index, table, [column])

    for table in reversed(KEYED_TABLES):
        op.drop_constraint(_fk_name(table), table, type_="foreignkey")
        op.create_foreign_key(f"{table}_user_id_fkey", table, "users", ["user_id"], ["id"])

    for table in reversed(RESUME_TABLES):
        op.drop_constraint(_fk_name(table), table, type_="foreignkey")
        op.alter_column(
            table,
            "user_id",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        )
