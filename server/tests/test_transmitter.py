import json
import pytest
from unittest.mock import patch

from common import generate_test_order
from constants import InvoiceStatus, OrderStatus
import transmitter
from database import db
from schemas import order_schema
from models import Order
from invoice_helpers import pay_invoice
import constants
import server


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


def assert_redis_call(mockredis, order):
    msg = order_schema.dump(order)
    mockredis.publish.assert_called_with(channel='transmissions',
                                         message=f'{json.dumps(msg)}')


@patch('orders.new_invoice')
def test_tx_resume(mock_new_invoice, client, mockredis):
    # Create two orders: one in transmitting state, the other in pending state.
    first_order_uuid = generate_test_order(
        mock_new_invoice, client,
        order_status=OrderStatus.transmitting)['uuid']
    first_db_order = Order.query.filter_by(uuid=first_order_uuid).first()

    second_order_uuid = generate_test_order(mock_new_invoice,
                                            client,
                                            order_id=2)['uuid']

    transmitter.tx_resume()
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
def test_tx_start(mock_new_invoice, client, mockredis):
    # Create two orders and pay only for the first.
    first_order_uuid = generate_test_order(mock_new_invoice, client)['uuid']
    second_order_uuid = generate_test_order(mock_new_invoice,
                                            client,
                                            order_id=2)['uuid']

    first_db_order = Order.query.filter_by(uuid=first_order_uuid).first()

    pay_invoice(first_db_order.invoices[0])
    assert_redis_call(mockredis, first_db_order)
    db.session.commit()

    # The expectation is that the first order gets transmitted and the second
    # stays untouched. The invoice callback handler should call tx_start.
    first_db_order = Order.query.filter_by(uuid=first_order_uuid).first()
    assert first_db_order.status == OrderStatus.transmitting.value
    assert first_db_order.tx_seq_num is not None

    second_db_order = Order.query.filter_by(uuid=second_order_uuid).first()
    assert second_db_order.status == OrderStatus.pending.value
    assert second_db_order.tx_seq_num is None

    # Calling tx_start explicitly won't change anything since the second order
    # is still unpaid
    transmitter.tx_start()
    second_db_order = Order.query.filter_by(uuid=second_order_uuid).first()
    assert second_db_order.status == OrderStatus.pending.value
    assert second_db_order.tx_seq_num is None


@patch('orders.new_invoice')
def test_assign_tx_seq_num(mock_new_invoice, client):
    # make some orders
    first_order_uuid = generate_test_order(mock_new_invoice, client)['uuid']
    first_db_order = Order.query.filter_by(uuid=first_order_uuid).first()
    assert first_db_order.tx_seq_num is None

    second_order_uuid = generate_test_order(mock_new_invoice,
                                            client,
                                            order_id=2)['uuid']
    second_db_order = Order.query.filter_by(uuid=second_order_uuid).first()
    assert second_db_order.tx_seq_num is None

    third_order_uuid = generate_test_order(mock_new_invoice,
                                           client,
                                           order_id=3)['uuid']
    third_db_order = Order.query.filter_by(uuid=third_order_uuid).first()
    assert third_db_order.tx_seq_num is None

    transmitter.assign_tx_seq_num(first_db_order)
    db.session.commit()
    first_db_order = Order.query.filter_by(uuid=first_order_uuid).first()
    assert first_db_order.tx_seq_num == 1

    transmitter.assign_tx_seq_num(second_db_order)
    db.session.commit()
    second_db_order = Order.query.filter_by(uuid=second_order_uuid).first()
    assert second_db_order.tx_seq_num == 2

    transmitter.assign_tx_seq_num(third_db_order)
    db.session.commit()
    third_db_order = Order.query.filter_by(uuid=third_order_uuid).first()
    assert third_db_order.tx_seq_num == 3


@patch('orders.new_invoice')
def test_start(mock_new_invoice, client, mockredis):
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

    # tx_resume() will finalize the completed order and call
    # tx_start() which leads to one of the paid orders being sent,
    # The tx_start() function method tries to send the other order
    # but it can't because the first sent order has not ended yet.
    # The direct call to tx_end() below will force ending the first
    # transmission and trigger the second transmission
    transmitter.tx_resume()
    transmitter.tx_start()
    first_sendable_db_order = \
        Order.query.filter_by(uuid=first_sendable_order_uuid).first()
    second_sendable_db_order = \
        Order.query.filter_by(uuid=second_sendable_order_uuid).first()
    assert first_sendable_db_order.status == OrderStatus.paid.value
    assert second_sendable_db_order.status == OrderStatus.transmitting.value
    transmitter.tx_end(second_sendable_db_order)

    completed_db_order = \
        Order.query.filter_by(uuid=completed_order_uuid).first()
    assert completed_db_order.status == OrderStatus.sent.value
    assert completed_db_order.ended_transmission_at is not None

    first_sendable_db_order = \
        Order.query.filter_by(uuid=first_sendable_order_uuid).first()
    second_sendable_db_order = \
        Order.query.filter_by(uuid=second_sendable_order_uuid).first()
    assert first_sendable_db_order.status ==\
        constants.OrderStatus.transmitting.value
    assert second_sendable_db_order.status ==\
        constants.OrderStatus.sent.value
    # The second order has a higher bid_per_byte, so it should be sent first
    assert first_sendable_db_order.tx_seq_num == 2
    assert second_sendable_db_order.tx_seq_num == 1
