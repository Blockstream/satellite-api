from datetime import datetime, timedelta
import os
import pytest
from unittest.mock import patch

from common import generate_test_order
from constants import InvoiceStatus, OrderStatus
from database import db
from models import Order, Invoice
import constants
import server
from worker_manager import cleanup_database


@pytest.fixture
def app():
    app = server.create_app(from_test=True)
    app.app_context().push()
    yield app
    server.teardown_app(app)


@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client


@patch('orders.new_invoice')
def test_cleanup_database(mock_new_invoice, client, app):
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

    cleanup_database(app)

    pending_db_invoice = \
        Invoice.query.filter_by(lid=pending_invoice_lid).first()
    assert pending_db_invoice.status == InvoiceStatus.expired.value

    pending_db_order = Order.query.filter_by(uuid=pending_order_uuid).first()
    assert pending_db_order.status == OrderStatus.expired.value

    message_path = os.path.join(constants.MSG_STORE_PATH, pending_order_uuid)
    assert not os.path.exists(message_path)

    message_path = os.path.join(constants.MSG_STORE_PATH, sent_order_uuid)
    assert not os.path.exists(message_path)
