from sqlalchemy.sql import func

from database import db


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    bid = db.Column(db.Integer, default=0)
    message_size = db.Column(db.Integer, nullable=False)
    bid_per_byte = db.Column(db.Float, default=0)  # TODO: remove (redundant)
    message_digest = db.Column(db.String(64), nullable=False)
    status = db.Column(db.Integer)
    uuid = db.Column(db.String(36), nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())
    cancelled_at = db.Column(db.DateTime)
    started_transmission_at = db.Column(db.DateTime)
    ended_transmission_at = db.Column(db.DateTime)
    tx_seq_num = db.Column(db.Integer, unique=True)
    unpaid_bid = db.Column(db.Integer, nullable=False)
    region_code = db.Column(db.Integer)
    invoices = db.relationship('Invoice', backref='order', lazy=True)


class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    lid = db.Column(db.String(100), nullable=False)
    invoice = db.Column(db.String(1024), nullable=False)
    paid_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=func.now())
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    status = db.Column(db.Integer)
    amount = db.Column(db.Integer)
    expires_at = db.Column(db.DateTime, nullable=False)


class TxConfirmation(db.Model):
    __tablename__ = 'tx_confirmations'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=func.now())
    order_id = db.Column(db.Integer,
                         db.ForeignKey('orders.id'),
                         nullable=False)
    region_id = db.Column(db.Integer, nullable=False)
    presumed = db.Column(db.Boolean, default=False)


class RxConfirmation(db.Model):
    __tablename__ = 'rx_confirmations'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=func.now())
    order_id = db.Column(db.Integer,
                         db.ForeignKey('orders.id'),
                         nullable=False)
    region_id = db.Column(db.Integer, nullable=False)
    presumed = db.Column(db.Boolean, default=False)


class TxRetry(db.Model):
    __tablename__ = 'tx_retries'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    last_attempt = db.Column(db.DateTime)
    retry_count = db.Column(db.Integer, default=0)
    region_code = db.Column(db.Integer)
    pending = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=func.now())
