"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_table('invitations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('token', sa.String(255), unique=True, nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('invited_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('is_used', sa.Boolean(), default=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_table('papers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('file_type', sa.String(10), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('uploaded_by', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_table('evaluation_tasks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('paper_id', sa.String(36), sa.ForeignKey('papers.id'), nullable=False),
        sa.Column('framework_id', sa.String(36), nullable=False),
        sa.Column('framework_path', sa.String(500), nullable=True),
        sa.Column('provider_names', sa.String(500), nullable=True),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_table('dimension_scores',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('evaluation_tasks.id'), nullable=False),
        sa.Column('dimension_key', sa.String(100), nullable=False),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('evidence_quotes', sa.JSON(), nullable=True),
        sa.Column('analysis', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_table('ai_call_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('evaluation_tasks.id'), nullable=False),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('dimension_key', sa.String(100), nullable=False),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('response_text', sa.Text(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_table('reliability_results',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('evaluation_tasks.id'), nullable=False),
        sa.Column('dimension_key', sa.String(100), nullable=False),
        sa.Column('mean_score', sa.Float(), nullable=False),
        sa.Column('std_score', sa.Float(), nullable=False),
        sa.Column('is_high_confidence', sa.Boolean(), nullable=False),
        sa.Column('model_scores', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_table('expert_reviews',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('evaluation_tasks.id'), nullable=False),
        sa.Column('expert_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )
    op.create_table('review_comments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('review_id', sa.String(36), sa.ForeignKey('expert_reviews.id'), nullable=False),
        sa.Column('dimension_key', sa.String(100), nullable=False),
        sa.Column('ai_score', sa.Float(), nullable=False),
        sa.Column('expert_score', sa.Float(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_table('reports',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('evaluation_tasks.id'), nullable=False),
        sa.Column('paper_id', sa.String(36), sa.ForeignKey('papers.id'), nullable=False),
        sa.Column('weighted_total', sa.Float(), nullable=False),
        sa.Column('report_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_table('report_exports',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('report_id', sa.String(36), sa.ForeignKey('reports.id'), nullable=False),
        sa.Column('export_type', sa.String(10), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_table('framework_versions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('framework_name', sa.String(255), nullable=False),
        sa.Column('version_tag', sa.String(50), nullable=True),
        sa.Column('yaml_content', sa.Text(), nullable=False),
        sa.Column('is_active', sa.String(1), default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('framework_versions')
    op.drop_table('report_exports')
    op.drop_table('reports')
    op.drop_table('review_comments')
    op.drop_table('expert_reviews')
    op.drop_table('reliability_results')
    op.drop_table('ai_call_logs')
    op.drop_table('dimension_scores')
    op.drop_table('evaluation_tasks')
    op.drop_table('papers')
    op.drop_table('invitations')
    op.drop_table('users')
