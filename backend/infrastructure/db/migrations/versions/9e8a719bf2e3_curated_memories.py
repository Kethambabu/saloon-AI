"""create curated_memories table

Revision ID: 9e8a719bf2e3
Revises: 6da0aee4c715
Create Date: 2026-07-18 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e8a719bf2e3'
down_revision: Union[str, Sequence[str], None] = '6da0aee4c715'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create curated_memories table
    op.create_table(
        'curated_memories',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.String(length=100), nullable=False, server_default='default'),
        sa.Column('scope', sa.String(length=50), nullable=False),
        sa.Column('owner_id', sa.String(length=255), nullable=True),
        sa.Column('agent_domains', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('source_event_id', sa.String(length=255), nullable=True),
        sa.Column('source_type', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('importance', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('consent_class', sa.String(length=50), nullable=False, server_default='standard'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('faiss_key', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_curated_memories_id'), 'curated_memories', ['id'], unique=False)
    op.create_index(op.f('ix_curated_memories_tenant_id'), 'curated_memories', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_curated_memories_scope'), 'curated_memories', ['scope'], unique=False)
    op.create_index(op.f('ix_curated_memories_status'), 'curated_memories', ['status'], unique=False)
    op.create_index(op.f('ix_curated_memories_owner_id'), 'curated_memories', ['owner_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_curated_memories_owner_id'), table_name='curated_memories')
    op.drop_index(op.f('ix_curated_memories_status'), table_name='curated_memories')
    op.drop_index(op.f('ix_curated_memories_scope'), table_name='curated_memories')
    op.drop_index(op.f('ix_curated_memories_tenant_id'), table_name='curated_memories')
    op.drop_index(op.f('ix_curated_memories_id'), table_name='curated_memories')
    op.drop_table('curated_memories')
