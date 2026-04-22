"""add pipeline fields

Revision ID: 003
Revises: 002
Create Date: 2026-04-16
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("papers", sa.Column("precheck_status", sa.String(length=20), nullable=True))
    op.add_column("papers", sa.Column("precheck_result", sa.JSON(), nullable=True))
    op.add_column("evaluation_tasks", sa.Column("failure_stage", sa.String(length=50), nullable=True))
    op.add_column("evaluation_tasks", sa.Column("failure_detail", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("evaluation_tasks", "failure_detail")
    op.drop_column("evaluation_tasks", "failure_stage")
    op.drop_column("papers", "precheck_result")
    op.drop_column("papers", "precheck_status")
