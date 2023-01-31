"""Add channel to order table

Revision ID: 3ec897840ea4
Revises: 0704901102eb
Create Date: 2022-04-05 21:57:27.398804

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '3ec897840ea4'
down_revision = '0704901102eb'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'orders',
        sa.Column('channel', sa.Integer, default=1, server_default='1'))


def downgrade():
    op.drop_column('orders', 'channel')
