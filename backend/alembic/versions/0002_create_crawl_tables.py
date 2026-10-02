"""Create crawl_targets and crawled_pages tables

Revision ID: 0002_create_crawl_tables
Revises: 0001_initial_system_table
Create Date: 2026-10-02 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002_create_crawl_tables'
down_revision: Union[str, None] = '0001_initial_system_table'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create crawl_targets table
    op.create_table(
        'crawl_targets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('normalized_url', sa.String(length=2048), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f('ix_crawl_targets_normalized_url'), 'crawl_targets', ['normalized_url'], unique=False)
    op.create_index(op.f('ix_crawl_targets_domain'), 'crawl_targets', ['domain'], unique=False)
    op.create_index(op.f('ix_crawl_targets_status'), 'crawl_targets', ['status'], unique=False)
    op.create_index('ix_crawl_targets_domain_status', 'crawl_targets', ['domain', 'status'], unique=False)

    # 2. Create crawled_pages table
    op.create_table(
        'crawled_pages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('crawl_target_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('final_url', sa.String(length=2048), nullable=False),
        sa.Column('depth', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=1024), nullable=True),
        sa.Column('content_markdown', sa.Text(), nullable=False, server_default=''),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('response_time_ms', sa.Float(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['crawl_target_id'], ['crawl_targets.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_crawled_pages_crawl_target_id'), 'crawled_pages', ['crawl_target_id'], unique=False)
    op.create_index(op.f('ix_crawled_pages_content_hash'), 'crawled_pages', ['content_hash'], unique=False)
    op.create_index('ix_crawled_pages_target_depth', 'crawled_pages', ['crawl_target_id', 'depth'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_crawled_pages_target_depth', table_name='crawled_pages')
    op.drop_index(op.f('ix_crawled_pages_content_hash'), table_name='crawled_pages')
    op.drop_index(op.f('ix_crawled_pages_crawl_target_id'), table_name='crawled_pages')
    op.drop_table('crawled_pages')

    op.drop_index('ix_crawl_targets_domain_status', table_name='crawl_targets')
    op.drop_index(op.f('ix_crawl_targets_status'), table_name='crawl_targets')
    op.drop_index(op.f('ix_crawl_targets_domain'), table_name='crawl_targets')
    op.drop_index(op.f('ix_crawl_targets_normalized_url'), table_name='crawl_targets')
    op.drop_table('crawl_targets')
