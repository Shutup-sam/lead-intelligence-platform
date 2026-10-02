"""Create multi-tenant SaaS tables: users, organizations, campaigns, usage, and foreign keys

Revision ID: 0006_create_multi_tenant_tables
Revises: 0005_create_jobs_table
Create Date: 2026-10-02 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0006_create_multi_tenant_tables'
down_revision: Union[str, None] = '0005_create_jobs_table'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 2. Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_organizations_slug', 'organizations', ['slug'], unique=True)

    # 3. Create organization_members table
    op.create_table(
        'organization_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='MEMBER'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('organization_id', 'user_id', name='uq_org_member'),
    )
    op.create_index('ix_organization_members_org_id', 'organization_members', ['organization_id'])
    op.create_index('ix_organization_members_user_id', 'organization_members', ['user_id'])

    # 4. Create campaigns table
    op.create_table(
        'campaigns',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='ACTIVE'),
        sa.Column('icp_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_campaigns_org_id', 'campaigns', ['organization_id'])
    op.create_index('ix_campaigns_org_status', 'campaigns', ['organization_id', 'status'])

    # 5. Create organization_usage_daily table
    op.create_table(
        'organization_usage_daily',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('crawls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pages_crawled', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('leads_created', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ai_qualifications', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('embeddings_generated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('jobs_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('jobs_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('estimated_ai_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('organization_id', 'date', name='uq_org_usage_date'),
    )
    op.create_index('ix_org_usage_org_id', 'organization_usage_daily', ['organization_id'])
    op.create_index('ix_org_usage_date', 'organization_usage_daily', ['date'])

    # 6. Add organization_id and campaign_id to crawl_targets
    op.add_column('crawl_targets', sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True))
    op.add_column('crawl_targets', sa.Column('campaign_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('campaigns.id', ondelete='SET NULL'), nullable=True))
    op.create_index('ix_crawl_targets_org_id', 'crawl_targets', ['organization_id'])
    op.create_index('ix_crawl_targets_campaign_id', 'crawl_targets', ['campaign_id'])
    op.create_index('ix_crawl_targets_org_status', 'crawl_targets', ['organization_id', 'status'])

    # 7. Add organization_id and campaign_id to leads
    op.add_column('leads', sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True))
    op.add_column('leads', sa.Column('campaign_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('campaigns.id', ondelete='SET NULL'), nullable=True))
    op.create_index('ix_leads_org_id', 'leads', ['organization_id'])
    op.create_index('ix_leads_campaign_id', 'leads', ['campaign_id'])
    op.create_index('ix_leads_org_status', 'leads', ['organization_id', 'status'])
    op.create_index('ix_leads_campaign_icp', 'leads', ['campaign_id', 'icp_score'])

    # 8. Add organization_id and campaign_id to jobs
    op.add_column('jobs', sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True))
    op.add_column('jobs', sa.Column('campaign_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('campaigns.id', ondelete='SET NULL'), nullable=True))
    op.create_index('ix_jobs_org_id', 'jobs', ['organization_id'])
    op.create_index('ix_jobs_campaign_id', 'jobs', ['campaign_id'])
    op.create_index('ix_jobs_org_status', 'jobs', ['organization_id', 'status'])

    # 9. Create default demo/development organization and associate existing records
    op.execute(
        """
        INSERT INTO organizations (id, name, slug, created_at, updated_at)
        VALUES ('00000000-0000-0000-0000-000000000001', 'Default Workspace', 'default-workspace', now(), now())
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute("UPDATE crawl_targets SET organization_id = '00000000-0000-0000-0000-000000000001' WHERE organization_id IS NULL")
    op.execute("UPDATE leads SET organization_id = '00000000-0000-0000-0000-000000000001' WHERE organization_id IS NULL")
    op.execute("UPDATE jobs SET organization_id = '00000000-0000-0000-0000-000000000001' WHERE organization_id IS NULL")


def downgrade() -> None:
    # Remove columns from jobs
    op.drop_index('ix_jobs_org_status', table_name='jobs')
    op.drop_index('ix_jobs_campaign_id', table_name='jobs')
    op.drop_index('ix_jobs_org_id', table_name='jobs')
    op.drop_column('jobs', 'campaign_id')
    op.drop_column('jobs', 'organization_id')

    # Remove columns from leads
    op.drop_index('ix_leads_campaign_icp', table_name='leads')
    op.drop_index('ix_leads_org_status', table_name='leads')
    op.drop_index('ix_leads_campaign_id', table_name='leads')
    op.drop_index('ix_leads_org_id', table_name='leads')
    op.drop_column('leads', 'campaign_id')
    op.drop_column('leads', 'organization_id')

    # Remove columns from crawl_targets
    op.drop_index('ix_crawl_targets_org_status', table_name='crawl_targets')
    op.drop_index('ix_crawl_targets_campaign_id', table_name='crawl_targets')
    op.drop_index('ix_crawl_targets_org_id', table_name='crawl_targets')
    op.drop_column('crawl_targets', 'campaign_id')
    op.drop_column('crawl_targets', 'organization_id')

    # Drop tables
    op.drop_table('organization_usage_daily')
    op.drop_table('campaigns')
    op.drop_table('organization_members')
    op.drop_table('organizations')
    op.drop_table('users')
