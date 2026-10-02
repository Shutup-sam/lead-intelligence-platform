"""Initial migration: pgvector extension and system metadata table

Revision ID: 0001_initial_system_table
Revises: 
Create Date: 2026-10-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001_initial_system_table'
down_revision: Union[str, None] = None
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    # Ensure vector extension is enabled in PostgreSQL
    op.execute('CREATE EXTENSION IF NOT EXISTS vector;')
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

    # Create system_metadata table
    op.create_table(
        'system_metadata',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f('ix_system_metadata_key'), 'system_metadata', ['key'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_system_metadata_key'), table_name='system_metadata')
    op.drop_table('system_metadata')
