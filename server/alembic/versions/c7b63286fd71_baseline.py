"""baseline

Revision ID: c7b63286fd71
Revises:
Create Date: 2021-05-27 21:56:12.258456

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = 'c7b63286fd71'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'orders' not in tables:
        op.create_table(
            'orders', sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('bid', sa.Integer, default=0),
            sa.Column('message_size', sa.Integer, nullable=False),
            sa.Column('bid_per_byte', sa.Float, default=0),
            sa.Column('message_digest', sa.String(64), nullable=False),
            sa.Column('status', sa.Integer),
            sa.Column('uuid', sa.String(36), nullable=False),
            sa.Column('created_at', sa.DateTime, default=sa.func.now()),
            sa.Column('cancelled_at', sa.DateTime),
            sa.Column('started_transmission_at', sa.DateTime),
            sa.Column('ended_transmission_at', sa.DateTime),
            sa.Column('tx_seq_num', sa.Integer, unique=True),
            sa.Column('unpaid_bid', sa.Integer, nullable=False))

    if 'invoices' not in tables:
        op.create_table(
            'invoices', sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('lid', sa.String(100), nullable=False),
            sa.Column('invoice', sa.String(1024), nullable=False),
            sa.Column('paid_at', sa.DateTime),
            sa.Column('created_at', sa.DateTime, default=sa.func.now()),
            sa.Column('order_id', sa.Integer, sa.ForeignKey('orders.id')),
            sa.Column('status', sa.Integer), sa.Column('amount', sa.Integer),
            sa.Column('expires_at', sa.DateTime, nullable=False))

    if 'tx_confirmations' not in tables:
        op.create_table(
            'tx_confirmations', sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('created_at', sa.DateTime, default=sa.func.now()),
            sa.Column('order_id', sa.Integer, sa.ForeignKey('orders.id')),
            sa.Column('region_id', sa.Integer),
            sa.Column('presumed', sa.Boolean, default=False))

    if 'rx_confirmations' not in tables:
        op.create_table(
            'rx_confirmations', sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('created_at', sa.DateTime, default=sa.func.now()),
            sa.Column('order_id', sa.Integer, sa.ForeignKey('orders.id')),
            sa.Column('region_id', sa.Integer),
            sa.Column('presumed', sa.Boolean, default=False))


def downgrade():
    op.drop_table('orders')
    op.drop_table('invoices')
    op.drop_table('tx_confirmations')
    op.drop_table('rx_confirmations')
