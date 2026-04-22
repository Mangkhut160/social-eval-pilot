"""add reporting and review fields

Revision ID: 004
Revises: 003
Create Date: 2026-04-16
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("reports", sa.Column("report_type", sa.String(length=20), nullable=True))
    op.add_column("reports", sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.execute("UPDATE reports SET report_type = 'internal' WHERE report_type IS NULL")
    op.alter_column("reports", "report_type", nullable=False)

    op.add_column("expert_reviews", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("evaluation_tasks", sa.Column("manual_review_requested", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("evaluation_tasks", "manual_review_requested")
    op.drop_column("expert_reviews", "version")
    op.drop_column("reports", "is_current")
    op.drop_column("reports", "report_type")
    op.drop_column("reports", "version")
