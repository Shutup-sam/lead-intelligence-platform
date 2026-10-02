"""Create jobs table

Revision ID: 0005_create_jobs_table
Revises: 0004_add_lead_status
Create Date: 2026-10-02 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0005_create_jobs_table'
down_revision: Union[str, None] = '0004_add_lead_status'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='QUEUED'),
        sa.Column('crawl_target_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('lead_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('current_stage', sa.String(length=100), nullable=False, server_default='queued'),
        sa.Column('pages_discovered', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pages_crawled', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['crawl_target_id'], ['crawl_targets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='SET NULL'),
    )

    op.create_index('ix_jobs_job_type', 'jobs', ['job_type'])
    op.create_index('ix_jobs_status', 'jobs', ['status'])
    op.create_index('ix_jobs_crawl_target_id', 'jobs', ['crawl_target_id'])
    op.create_index('ix_jobs_lead_id', 'jobs', ['lead_id'])
    op.create_index('ix_jobs_idempotency_key', 'jobs', ['idempotency_key'])
    op.create_index('ix_jobs_type_status', 'jobs', ['job_type', 'status'])
    op.create_index('ix_jobs_target_status', 'jobs', ['crawl_target_id', 'status'])


def downgrade() -> None:
    op.drop_index('ix_jobs_target_status', table_name='jobs')
    op.drop_index('ix_jobs_type_status', table_name='jobs')
    op.drop_index('ix_jobs_idempotency_key', table_name='jobs')
    op.drop_index('ix_jobs_lead_id', table_name='jobs')
    op.drop_index('ix_jobs_crawl_target_id', table_name='jobs')
    op.drop_index('ix_jobs_status', table_name='jobs')
    op.drop_index('ix_jobs_job_type', table_name='jobs')
    op.drop_table('jobs')
