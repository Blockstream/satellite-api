import json
import pytest
from unittest.mock import patch

from common import generate_test_order
from constants import InvoiceStatus, OrderStatus
from transmitter import TxEngine
from database import db
from schemas import order_schema

from models import Order
from invoice_helpers import pay_invoice
import server


@pytest.fixture
def mockredis(mocker):
    _mr = mocker.Mock(name="mockredis")
    mocker.patch("transmitter.redis", return_value=_mr)
    mocker.patch("transmitter.redis.from_url", return_value=_mr)
    return _mr


@pytest.fixture
def app(mockredis):
    app = server.create_app(from_test=True)
    app.app_context().push()
    yield app
    server.teardown_app(app)


@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client


@pytest.fixture
def tx_engine():
    tx_engine = TxEngine()
    yield tx_engine


def assert_redis_call(mockredis, order):
    msg = order_schema.dump(order)
    mockredis.publish.assert_called_with(channel='transmissions',
                                         message=f'{json.dumps(msg)}')


@patch('orders.new_invoice')
def test_tx_resume(mock_new_invoice, client, tx_engine, mockredis):
    # Create two orders: one in transmitting state, the other in pending state.
    first_order_uuid = generate_test_order(
        mock_new_invoice, client,
        order_status=OrderStatus.transmitting)['uuid']
    first_db_order = Order.query.filter_by(uuid=first_order_uuid).first()

    second_order_uuid = generate_test_order(mock_new_invoice,
                                            client,
                                            order_id=2)['uuid']

    tx_engine.tx_resume()
    assert_redis_call(mockredis, first_db_order)

    # The expectation is that the transmitting order changes to sent. The other
    # order should remain untouched.
    first_db_order = Order.query.filter_by(uuid=first_order_uuid).first()
    assert first_db_order.status == OrderStatus.sent.value
    assert first_db_order.ended_transmission_at is not None

    second_db_order = Order.query.filter_by(uuid=second_order_uuid).first()
    assert second_db_order.status == OrderStatus.pending.value
    assert second_db_order.ended_transmission_at is None


@patch('orders.new_invoice')
def test_tx_start(mock_new_invoice, client, tx_engine, mockredis):
    # Create two orders and pay only for the first.
    first_order_uuid = generate_test_order(mock_new_invoice, client)['uuid']
    second_order_uuid = generate_test_order(
        mock_new_invoice,
        client,
        order_id=2,
        invoice_status=InvoiceStatus.paid)['uuid']

    first_db_order = Order.query.filter_by(uuid=first_order_uuid).first()
    pay_invoice(first_db_order.invoices[0])
    db.session.commit()
    second_db_order = Order.query.filter_by(uuid=first_order_uuid).first()

    tx_engine.tx_start(first_db_order)
    tx_engine.tx_start(second_db_order)
    assert_redis_call(mockredis, first_db_order)
    assert_redis_call(mockredis, second_db_order)

    # The expectation is that the first order gets transmitted and the second
    # order stays untouched.
    first_db_order = Order.query.filter_by(uuid=first_order_uuid).first()
    assert first_db_order.status == OrderStatus.transmitting.value
    assert first_db_order.tx_seq_num is not None

    second_db_order = Order.query.filter_by(uuid=second_order_uuid).first()
    assert second_db_order.status == OrderStatus.pending.value
    assert second_db_order.tx_seq_num is None


@patch('orders.new_invoice')
def test_assign_tx_seq_num(mock_new_invoice, client, tx_engine):
    # make some orders
    first_order_uuid = generate_test_order(
        mock_new_invoice, client, invoice_status=InvoiceStatus.paid)['uuid']
    first_db_order = Order.query.filter_by(uuid=first_order_uuid).first()
    assert first_db_order.tx_seq_num is None

    second_order_uuid = generate_test_order(
        mock_new_invoice,
        client,
        order_id=2,
        invoice_status=InvoiceStatus.paid)['uuid']
    second_db_order = Order.query.filter_by(uuid=second_order_uuid).first()
    assert second_db_order.tx_seq_num is None

    third_order_uuid = generate_test_order(
        mock_new_invoice,
        client,
        order_id=3,
        invoice_status=InvoiceStatus.paid)['uuid']
    third_db_order = Order.query.filter_by(uuid=third_order_uuid).first()
    assert third_db_order.tx_seq_num is None

    tx_engine.assign_tx_seq_num(first_db_order)
    db.session.commit()
    first_db_order = Order.query.filter_by(uuid=first_order_uuid).first()
    assert first_db_order.tx_seq_num == 1

    tx_engine.assign_tx_seq_num(second_db_order)
    db.session.commit()
    second_db_order = Order.query.filter_by(uuid=second_order_uuid).first()
    assert second_db_order.tx_seq_num == 2

    tx_engine.assign_tx_seq_num(third_db_order)
    db.session.commit()
    third_db_order = Order.query.filter_by(uuid=third_order_uuid).first()
    assert third_db_order.tx_seq_num == 3
