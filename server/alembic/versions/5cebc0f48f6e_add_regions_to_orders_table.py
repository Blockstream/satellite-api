"""Add regions to orders table

Revision ID: 5cebc0f48f6e
Revises: c7b63286fd71
Create Date: 2021-07-26 22:38:41.193023

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '5cebc0f48f6e'
down_revision = 'c7b63286fd71'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('orders', sa.Column('region_code', sa.Integer))


def downgrade():
    op.drop_column('orders', 'region_code')
