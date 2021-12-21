"""Add tx_retries table

Revision ID: 0704901102eb
Revises: 5cebc0f48f6e
Create Date: 2021-08-02 21:46:46.095406

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0704901102eb'
down_revision = '5cebc0f48f6e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tx_retries', sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('order_id', sa.Integer, sa.ForeignKey('orders.id')),
        sa.Column('last_attempt', sa.DateTime),
        sa.Column('retry_count', sa.Integer, default=0),
        sa.Column('region_code', sa.Integer),
        sa.Column('pending', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()))


def downgrade():
    op.drop_table('tx_retries')
