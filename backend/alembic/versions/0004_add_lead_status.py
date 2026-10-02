"""Add status column to leads table

Revision ID: 0004_add_lead_status
Revises: 0003_create_lead_tables
Create Date: 2026-10-02 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0004_add_lead_status'
down_revision: Union[str, None] = '0003_create_lead_tables'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'leads',
        sa.Column('status', sa.String(length=50), nullable=False, server_default='NEW'),
    )
    op.create_index('ix_leads_status', 'leads', ['status'])
    op.create_index('ix_leads_status_icp', 'leads', ['status', 'icp_score'])


def downgrade() -> None:
    op.drop_index('ix_leads_status_icp', table_name='leads')
    op.drop_index('ix_leads_status', table_name='leads')
    op.drop_column('leads', 'status')
