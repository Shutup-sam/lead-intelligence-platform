"""Create leads, lead_signals, lead_embeddings, and llm_audit_logs tables

Revision ID: 0003_create_leads_and_embeddings_tables
Revises: 0002_create_crawl_tables
Create Date: 2026-10-02 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '0003_create_lead_tables'
down_revision: Union[str, None] = '0002_create_crawl_tables'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create leads table
    op.create_table(
        'leads',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('crawl_target_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('company_summary', sa.Text(), nullable=False),
        sa.Column('value_proposition', sa.Text(), nullable=False),
        sa.Column('industry', sa.String(length=100), nullable=False),
        sa.Column('target_audience', sa.Text(), nullable=False),
        sa.Column('business_model', sa.String(length=100), nullable=False),
        sa.Column('geography', sa.String(length=100), nullable=False),
        sa.Column('estimated_company_size', sa.String(length=50), nullable=False),
        sa.Column('technology_signals', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('icp_score', sa.Integer(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('qualification_reasoning', sa.Text(), nullable=False),
        sa.Column('qualification_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['crawl_target_id'], ['crawl_targets.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_leads_crawl_target_id'), 'leads', ['crawl_target_id'], unique=False)
    op.create_index(op.f('ix_leads_domain'), 'leads', ['domain'], unique=False)
    op.create_index(op.f('ix_leads_industry'), 'leads', ['industry'], unique=False)
    op.create_index(op.f('ix_leads_icp_score'), 'leads', ['icp_score'], unique=False)
    op.create_index('ix_leads_domain_icp', 'leads', ['domain', 'icp_score'], unique=False)
    op.create_index('ix_leads_industry_icp', 'leads', ['industry', 'icp_score'], unique=False)

    # 2. Create lead_signals table
    op.create_table(
        'lead_signals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('lead_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('signal', sa.String(length=255), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=False),
        sa.Column('source_url', sa.String(length=2048), nullable=True),
        sa.Column('sentiment', sa.String(length=50), nullable=False, server_default='positive'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_lead_signals_lead_id'), 'lead_signals', ['lead_id'], unique=False)

    # 3. Create lead_embeddings table
    op.create_table(
        'lead_embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('lead_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('embedding', Vector(1536), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_lead_embeddings_lead_id'), 'lead_embeddings', ['lead_id'], unique=False)
    op.create_index(op.f('ix_lead_embeddings_content_hash'), 'lead_embeddings', ['content_hash'], unique=False)
    # Native HNSW cosine index for pgvector
    op.execute(
        "CREATE INDEX ix_lead_embeddings_hnsw ON lead_embeddings USING hnsw (embedding vector_cosine_ops);"
    )

    # 4. Create llm_audit_logs table
    op.create_table(
        'llm_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('lead_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('latency_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('request_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_llm_audit_logs_lead_id'), 'llm_audit_logs', ['lead_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_llm_audit_logs_lead_id'), table_name='llm_audit_logs')
    op.drop_table('llm_audit_logs')

    op.execute("DROP INDEX IF EXISTS ix_lead_embeddings_hnsw;")
    op.drop_index(op.f('ix_lead_embeddings_content_hash'), table_name='lead_embeddings')
    op.drop_index(op.f('ix_lead_embeddings_lead_id'), table_name='lead_embeddings')
    op.drop_table('lead_embeddings')

    op.drop_index(op.f('ix_lead_signals_lead_id'), table_name='lead_signals')
    op.drop_table('lead_signals')

    op.drop_index('ix_leads_industry_icp', table_name='leads')
    op.drop_index('ix_leads_domain_icp', table_name='leads')
    op.drop_index(op.f('ix_leads_icp_score'), table_name='leads')
    op.drop_index(op.f('ix_leads_industry'), table_name='leads')
    op.drop_index(op.f('ix_leads_domain'), table_name='leads')
    op.drop_index(op.f('ix_leads_crawl_target_id'), table_name='leads')
    op.drop_table('leads')
