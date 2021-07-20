from datetime import datetime, timedelta
import os
import pytest
from unittest.mock import patch

from common import generate_test_order
from constants import InvoiceStatus, OrderStatus
import daemon
from database import db
from models import Order, Invoice
from invoice_helpers import pay_invoice
import constants
import server


@pytest.fixture
def tx_engine(mocker):
    tx_engine = daemon.TxEngine()
    yield tx_engine


@pytest.fixture
def mockredis(mocker):
    _mr = mocker.Mock(name="mockredis")
    mocker.patch("transmitter.redis", return_value=_mr)
    mocker.patch("transmitter.redis.from_url", return_value=_mr)
    return _mr


@pytest.fixture
def client(mockredis):
    app = server.create_app(from_test=True)
    app.app_context().push()
    with app.test_client() as client:
        yield client
    server.teardown_app(app)


@pytest.fixture
def daemon_app():
    app = daemon.create_app()
    yield app


@patch('orders.new_invoice')
def test_tx_engine(mock_new_invoice, client, tx_engine):
    # prepare test env

    # create an old transmitted order
    completed_order_uuid = generate_test_order(
        mock_new_invoice,
        client,
        invoice_status=InvoiceStatus.paid,
        order_status=OrderStatus.transmitting)['uuid']

    # create two sendable orders
    first_sendable_order_uuid = generate_test_order(mock_new_invoice,
                                                    client,
                                                    order_id=5,
                                                    bid=1000)['uuid']
    first_sendable_db_order = \
        Order.query.filter_by(uuid=first_sendable_order_uuid).first()
    pay_invoice(first_sendable_db_order.invoices[0])
    db.session.commit()

    second_sendable_order_uuid = generate_test_order(mock_new_invoice,
                                                     client,
                                                     order_id=6,
                                                     bid=2000)['uuid']
    second_sendable_db_order = \
        Order.query.filter_by(uuid=second_sendable_order_uuid).first()
    pay_invoice(second_sendable_db_order.invoices[0])
    db.session.commit()

    tx_engine.start(2)

    completed_db_order = \
        Order.query.filter_by(uuid=completed_order_uuid).first()
    assert completed_db_order.status == OrderStatus.sent.value
    assert completed_db_order.ended_transmission_at is not None

    first_sendable_db_order = \
        Order.query.filter_by(uuid=first_sendable_order_uuid).first()
    second_sendable_db_order = \
        Order.query.filter_by(uuid=second_sendable_order_uuid).first()
    assert first_sendable_db_order.status == constants.OrderStatus.sent.value
    assert second_sendable_db_order.status == constants.OrderStatus.sent.value
    # The second order has a higher bid_per_byte, so it should be sent first
    assert first_sendable_db_order.tx_seq_num == 2
    assert second_sendable_db_order.tx_seq_num == 1
    assert second_sendable_db_order.ended_transmission_at \
        < first_sendable_db_order.ended_transmission_at


@patch('orders.new_invoice')
def test_cleanup_database(mock_new_invoice, client, tx_engine, daemon_app):
    # prepare test env

    # create an invoice that must get expired
    pending_invoice_lid = generate_test_order(
        mock_new_invoice, client, order_id=2)['lightning_invoice']['id']
    pending_db_invoice = \
        Invoice.query.filter_by(lid=pending_invoice_lid).first()
    pending_db_invoice.expires_at = datetime.utcnow() - timedelta(days=1)
    db.session.commit()

    # create an order that must get expired
    pending_order_uuid = generate_test_order(mock_new_invoice,
                                             client,
                                             order_id=3)['uuid']
    pending_db_order = Order.query.filter_by(uuid=pending_order_uuid).first()
    pending_db_order.created_at = datetime.utcnow() - \
        timedelta(days=constants.EXPIRE_PENDING_ORDERS_AFTER_DAYS
                  + 1)
    db.session.commit()

    # Create an order whose transmission ended a long time ago. The
    # corresponding message file should be deleted.
    sent_order_uuid = generate_test_order(
        mock_new_invoice,
        client,
        order_id=4,
        invoice_status=InvoiceStatus.paid)['uuid']
    sent_db_order = Order.query.filter_by(uuid=sent_order_uuid).first()
    sent_db_order.ended_transmission_at = datetime.utcnow() -\
        timedelta(days=constants.MESSAGE_FILE_RETENTION_TIME_DAYS
                  + 1)
    db.session.commit()

    daemon.cleanup_database(daemon_app)

    pending_db_invoice = \
        Invoice.query.filter_by(lid=pending_invoice_lid).first()
    assert pending_db_invoice.status == InvoiceStatus.expired.value

    pending_db_order = Order.query.filter_by(uuid=pending_order_uuid).first()
    assert pending_db_order.status == OrderStatus.expired.value

    message_path = os.path.join(constants.MSG_STORE_PATH, pending_order_uuid)
    assert not os.path.exists(message_path)

    message_path = os.path.join(constants.MSG_STORE_PATH, sent_order_uuid)
    assert not os.path.exists(message_path)
