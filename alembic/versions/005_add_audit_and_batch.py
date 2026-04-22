"""add audit and batch tables

Revision ID: 005
Revises: 004
Create Date: 2026-04-16
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("object_type", sa.String(length=50), nullable=False),
        sa.Column("object_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("result", sa.String(length=50), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "batch_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.add_column("evaluation_tasks", sa.Column("batch_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_evaluation_tasks_batch_id",
        "evaluation_tasks",
        "batch_tasks",
        ["batch_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_evaluation_tasks_batch_id", "evaluation_tasks", type_="foreignkey")
    op.drop_column("evaluation_tasks", "batch_id")
    op.drop_table("batch_tasks")
    op.drop_table("audit_logs")
