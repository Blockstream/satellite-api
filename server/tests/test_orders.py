import uuid
import random
from datetime import datetime, timedelta
from http import HTTPStatus
from time import sleep
from unittest.mock import patch

import pytest

from constants import InvoiceStatus, OrderStatus
from database import db
from models import Order
from invoice_helpers import pay_invoice
import bidding
import constants
import server

from common import new_invoice, place_order, generate_test_order
from error import assert_error


@pytest.fixture
def client(mockredis):
    app = server.create_app(from_test=True)
    app.app_context().push()
    with app.test_client() as client:
        yield client
    server.teardown_app(app)


@pytest.mark.parametrize("state", ['pending', 'queued', 'sent'])
@pytest.mark.parametrize("param", ['before', 'after'])
def test_get_orders_invalid_before_after_parameter(client, param, state):
    get_rv = client.get(f'/orders/{state}?{param}=')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?{param}=sometext')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?{param}=2021-13-11')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?{param}=2021.05.10')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?{param}=2021-05-1a0T19:51:45')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?{param}=2021.05.10T19:51:45')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?{param}=2021-05-10T25:51:45')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?{param}=2021-05-10T22:51:45')
    assert get_rv.status_code == HTTPStatus.OK
    # before and before_delta together should not be allowed. Same for after
    # and after_delta.
    get_rv = client.get(
        f'/orders/{state}?{param}=2021-05-10T22:51:45&{param}_delta=5')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.parametrize("state", ['pending', 'queued', 'sent'])
@pytest.mark.parametrize("param", ['before', 'after'])
def test_get_orders_invalid_before_after_delta_parameter(client, param, state):
    get_rv = client.get(f'/orders/{state}?{param}_delta=')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?{param}_delta=sometext')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?{param}_delta=2021-05-10T25:51:45')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?{param}_delta=5.2')  # float
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?{param}_delta=5')
    assert get_rv.status_code == HTTPStatus.OK
    # before and before_delta together should not be allowed. Same for after
    # and after_delta.
    get_rv = client.get(
        f'/orders/{state}?{param}_delta=5&{param}=2021-05-10T22:51:45')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.parametrize("state", ['pending', 'queued', 'sent'])
def test_get_orders_invalid_limit(client, state):
    get_rv = client.get(f'/orders/{state}?limit=')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?limit=sometext')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?limit=1a2')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?limit=-1')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?limit=1.2')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST


def test_try_to_get_invalid_order_state(client):
    for state in ['pendiing', 'someendpoint', 'Pending']:
        get_rv = client.get(f'/orders/{state}')
        assert get_rv.status_code == HTTPStatus.NOT_FOUND


@patch('constants.PAGE_SIZE', 3)  # change PAGE_SIZE to run this test faster
@pytest.mark.parametrize("state", ['pending', 'queued', 'sent'])
def test_get_orders_date_filtering_parameters(client, state):
    # Create PAGE_SIZE orders with a fixed interval between them
    n_orders = constants.PAGE_SIZE
    order_interval_sec = 60  # interval between consecutive orders
    order_creation_timestamps = []
    order_uuids = []
    order_status = OrderStatus.transmitting.value if \
        state == 'queued' else OrderStatus[state].value
    for i in range(n_orders):
        order = Order(uuid=str(uuid.uuid4()),
                      unpaid_bid=1000,
                      message_size=10,
                      message_digest=str(uuid.uuid4()),
                      status=order_status,
                      created_at=datetime.utcnow() -
                      timedelta(seconds=i * order_interval_sec))
        db.session.add(order)
        order_creation_timestamps.append(order.created_at)
        order_uuids.append(order.uuid)
    db.session.commit()

    # Fetch orders excluding the most recent
    before = order_creation_timestamps[0].isoformat()
    get_rv = client.get(f'/orders/{state}?before={before}')
    assert get_rv.status_code == HTTPStatus.OK
    assert [x['uuid'] for x in get_rv.get_json()] == order_uuids[1:]

    # Fetch orders excluding the oldest
    after = order_creation_timestamps[-1].isoformat()
    get_rv = client.get(f'/orders/{state}?after={after}')
    assert get_rv.status_code == HTTPStatus.OK
    assert [x['uuid'] for x in get_rv.get_json()] == order_uuids[:-1]

    # Fetch the two orders in the middle
    get_rv = client.get(f'/orders/{state}?after={after}&before={before}')
    assert get_rv.status_code == HTTPStatus.OK
    assert [x['uuid'] for x in get_rv.get_json()] == order_uuids[1:-1]

    # Try the same using the delta parameters

    # Fetch orders excluding the most recent
    before_delta = order_interval_sec - 10
    get_rv = client.get(f'/orders/{state}?before_delta={before_delta}')
    assert get_rv.status_code == HTTPStatus.OK
    assert [x['uuid'] for x in get_rv.get_json()] == order_uuids[1:]

    # Fetch orders excluding the oldest
    after_delta = (n_orders - 1) * order_interval_sec - 10
    get_rv = client.get(f'/orders/{state}?after_delta={after_delta}')
    assert get_rv.status_code == HTTPStatus.OK
    assert [x['uuid'] for x in get_rv.get_json()] == order_uuids[:-1]

    # Fetch the two orders in the middle
    get_rv = client.get(f'/orders/{state}?after_delta={after_delta}&' +
                        f'before_delta={before_delta}')
    assert get_rv.status_code == HTTPStatus.OK
    assert [x['uuid'] for x in get_rv.get_json()] == order_uuids[1:-1]


@patch('orders.new_invoice')
@pytest.mark.parametrize("state", ['pending', 'queued', 'sent'])
def test_get_orders_limit_parameter(mock_new_invoice, client, state):
    n_bytes = 500
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bidding.get_min_bid(n_bytes)))
    for i in range(constants.MAX_PAGE_SIZE + 1):
        post_rv = place_order(client, n_bytes)
        assert post_rv.status_code == HTTPStatus.OK
        uuid = post_rv.get_json()['uuid']
        db_order = Order.query.filter_by(uuid=uuid).first()
        db_order.status = OrderStatus.transmitting.value if \
            state == 'queued' else OrderStatus[state].value
        db.session.commit()

    # no limit parameter, max PAGE_SIZE should be returned
    get_rv = client.get(f'/orders/{state}')
    assert get_rv.status_code == HTTPStatus.OK
    get_json_resp = get_rv.get_json()
    assert len(get_json_resp) == constants.PAGE_SIZE

    # with limit parameter present
    get_rv = client.get(f'/orders/{state}?limit=10')
    assert get_rv.status_code == HTTPStatus.OK
    get_json_resp = get_rv.get_json()
    assert len(get_json_resp) == 10

    # the limit should be within [1, MAX_PAGE_SIZE]
    get_rv = client.get(f'/orders/{state}?limit={constants.MAX_PAGE_SIZE}')
    assert get_rv.status_code == HTTPStatus.OK
    get_json_resp = get_rv.get_json()
    assert len(get_json_resp) == constants.MAX_PAGE_SIZE
    get_rv = client.get(f'/orders/{state}?limit={constants.MAX_PAGE_SIZE + 1}')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?limit=0')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST


@patch('orders.new_invoice')
@pytest.mark.parametrize("state", ['pending', 'queued', 'sent'])
@pytest.mark.parametrize("channel", constants.CHANNELS)
def test_get_orders_channel_parameter(mock_new_invoice, client, state,
                                      channel):
    n_bytes = 500
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bidding.get_min_bid(n_bytes)))
    # Place all orders as the admin
    for i in range(constants.MAX_PAGE_SIZE + 1):
        post_rv = place_order(client, n_bytes, channel=channel, admin=True)
        assert post_rv.status_code == HTTPStatus.OK
        uuid = post_rv.get_json()['uuid']
        db_order = Order.query.filter_by(uuid=uuid).first()
        db_order.status = OrderStatus.transmitting.value if \
            state == 'queued' else OrderStatus[state].value
        db.session.commit()

    # Get the orders of each channel as a regular user
    for _channel in constants.CHANNELS:
        get_rv = client.get(f'/orders/{state}?channel={_channel}')
        if 'get' in constants.CHANNEL_INFO[_channel].user_permissions:
            assert get_rv.status_code == HTTPStatus.OK
            get_json_resp = get_rv.get_json()
            n_expected_res = constants.PAGE_SIZE if _channel == channel else 0
            assert len(get_json_resp) == n_expected_res
        else:
            assert get_rv.status_code == HTTPStatus.UNAUTHORIZED
            assert_error(get_rv.get_json(), 'ORDER_CHANNEL_UNAUTHORIZED_OP')

    # Get the orders of each channel as an admin user
    for _channel in constants.CHANNELS:
        get_rv = client.get(f'/admin/orders/{state}?channel={_channel}')
        assert get_rv.status_code == HTTPStatus.OK
        get_json_resp = get_rv.get_json()
        n_expected_res = constants.PAGE_SIZE if _channel == channel else 0
        assert len(get_json_resp) == n_expected_res


@patch('orders.new_invoice')
def test_get_pending_orders(mock_new_invoice, client):
    # make some orders
    uuid_order1 = generate_test_order(mock_new_invoice, client)['uuid']
    uuid_order2 = generate_test_order(mock_new_invoice, client)['uuid']
    # manipulate order status for testing the GET /orders endpoint
    db_order = Order.query.filter_by(uuid=uuid_order2).first()
    pay_invoice(db_order.invoices[0])
    db.session.commit()

    sleep(1.0)  # to have different created_at
    uuid_order3 = generate_test_order(mock_new_invoice, client)['uuid']

    get_rv = client.get('/orders/pending')
    assert get_rv.status_code == HTTPStatus.OK
    get_json_resp = get_rv.get_json()
    assert len(get_json_resp) == 2  # paid order should be filtered out
    assert get_json_resp[0]['uuid'] == uuid_order3
    assert get_json_resp[1]['uuid'] == uuid_order1


@patch('orders.new_invoice')
@patch('constants.PAGE_SIZE', 3)  # change PAGE_SIZE to run this test faster
def test_get_pending_orders_paging(mock_new_invoice, client):
    # make more orders than PAGE_SIZE
    n_orders = constants.PAGE_SIZE + 2
    n_bytes = 500
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bidding.get_min_bid(n_bytes)))
    order_uuids = []
    for i in range(n_orders):
        post_rv = place_order(client, n_bytes)
        assert post_rv.status_code == HTTPStatus.OK
        order_uuids.append(post_rv.get_json()['uuid'])
        sleep(1.0)  # to have different created_at

    # Check all orders were created
    all_orders = Order.query.filter_by(status=OrderStatus.pending.value).all()
    assert len(all_orders) == n_orders

    # Fetch the pending orders with paging
    get_rv = client.get('/orders/pending')
    assert get_rv.status_code == HTTPStatus.OK
    get_json_resp = get_rv.get_json()

    # Only the last PAGE_SIZE orders should be returned
    assert len(get_json_resp) == constants.PAGE_SIZE
    expected_uuids = order_uuids[-constants.PAGE_SIZE:]
    expected_uuids.reverse()  # match the sorting from newest to oldest
    for i in range(constants.PAGE_SIZE):
        assert get_json_resp[i]['uuid'] == expected_uuids[i]


@patch('orders.new_invoice')
def test_get_queued_orders(mock_new_invoice, client):
    # Create some orders with different states
    order = {}
    for state in [
            'pending', 'paid', 'transmitting', 'sent', 'received', 'confirming'
    ]:
        order[state] = generate_test_order(mock_new_invoice,
                                           client,
                                           order_status=OrderStatus[state])

    # Request queued orders
    get_rv = client.get('/orders/queued')
    assert get_rv.status_code == HTTPStatus.OK
    queued_uuids = [order['uuid'] for order in get_rv.get_json()]

    # The expectation is that only paid, transmitting and confirming
    # orders are returned
    assert len(queued_uuids) == 3
    assert order['pending']['uuid'] not in queued_uuids
    assert order['paid']['uuid'] in queued_uuids
    assert order['transmitting']['uuid'] in queued_uuids
    assert order['sent']['uuid'] not in queued_uuids
    assert order['received']['uuid'] not in queued_uuids
    assert order['confirming']['uuid'] in queued_uuids


@patch('orders.new_invoice')
def test_get_queued_orders_sorting(mock_new_invoice, client):
    n_bytes = 500
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bidding.get_min_bid(n_bytes)))
    n_orders = 10
    bid_per_byte_map = {}
    for i in range(n_orders):
        post_rv = place_order(client, n_bytes)
        assert post_rv.status_code == HTTPStatus.OK
        order_uuid = post_rv.get_json()['uuid']
        db_order = Order.query.filter_by(uuid=order_uuid).first()
        db_order.status = OrderStatus.transmitting.value
        bid_per_byte = random.randint(1, 10000)
        bid_per_byte_map[order_uuid] = bid_per_byte
        db_order.bid_per_byte = bid_per_byte
        db.session.commit()

    expected_sorted_orders = sorted(bid_per_byte_map.items(),
                                    key=lambda x: x[1],
                                    reverse=True)

    get_rv = client.get('/orders/queued')
    assert get_rv.status_code == HTTPStatus.OK
    get_json_resp = get_rv.get_json()
    assert len(get_json_resp) == n_orders
    for i in range(n_orders):
        assert get_json_resp[i]['uuid'] == expected_sorted_orders[i][0]
        assert get_json_resp[i]['bid_per_byte'] == expected_sorted_orders[i][1]


@patch('orders.new_invoice')
def test_get_sent_orders(mock_new_invoice, client):
    # Create some orders with different states
    order = {}
    for state in ['pending', 'transmitting', 'sent', 'received']:
        order[state] = generate_test_order(mock_new_invoice,
                                           client,
                                           order_status=OrderStatus[state])

    # Request sent orders
    get_rv = client.get('/orders/sent')
    assert get_rv.status_code == HTTPStatus.OK
    get_json_resp = get_rv.get_json()
    sent_uuids = [order['uuid'] for order in get_rv.get_json()]

    # The expectation is that only sent and received orders are returned
    assert len(get_json_resp) == 2  # pending order should be filtered
    assert order['pending']['uuid'] not in sent_uuids
    assert order['transmitting']['uuid'] not in sent_uuids
    assert order['sent']['uuid'] in sent_uuids
    assert order['received']['uuid'] in sent_uuids


@patch('orders.new_invoice')
def test_get_sent_orders_sorting(mock_new_invoice, client):
    n_bytes = 500
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bidding.get_min_bid(n_bytes)))
    order_uuids = []
    for i in range(5):
        post_rv = place_order(client, n_bytes)
        assert post_rv.status_code == HTTPStatus.OK
        post_json_resp = post_rv.get_json()
        order_uuid = post_json_resp['uuid']
        order_uuids.append(order_uuid)
        db_order = Order.query.filter_by(uuid=order_uuid).first()
        db_order.status = OrderStatus.sent.value
        order_created_at = db_order.created_at
        db_order.ended_transmission_at = order_created_at + timedelta(0, 100)
        db.session.commit()
        sleep(1.0)  # to have different created_at

    order_uuids.reverse()  # expected uuid order in the response
    get_rv = client.get('/orders/sent')
    assert get_rv.status_code == HTTPStatus.OK
    get_json_resp = get_rv.get_json()
    assert len(get_json_resp) == 5
    for i in range(5):
        assert get_json_resp[i]['uuid'] == order_uuids[i]


@patch('orders.new_invoice')
@patch('constants.PAGE_SIZE', 3)  # change PAGE_SIZE to run this test faster
def test_get_sent_orders_paging(mock_new_invoice, client):
    # make more orders than PAGE_SIZE
    n_orders = constants.PAGE_SIZE + 2
    n_bytes = 500
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bidding.get_min_bid(n_bytes)))
    order_uuids = []
    for i in range(n_orders):
        post_rv = place_order(client, n_bytes)
        assert post_rv.status_code == HTTPStatus.OK
        order_uuid = post_rv.get_json()['uuid']
        order_uuids.append(order_uuid)
        db_order = Order.query.filter_by(uuid=order_uuid).first()
        db_order.status = OrderStatus.received.value
        order_created_at = db_order.created_at
        db_order.ended_transmission_at = order_created_at + timedelta(0, 100)
        db.session.commit()
        sleep(1.0)  # to have different created_at

    # Check all orders were created
    all_orders = Order.query.filter_by(status=OrderStatus.received.value).all()
    assert len(all_orders) == n_orders

    # Fetch the sent orders with paging
    get_rv = client.get('/orders/sent')
    assert get_rv.status_code == HTTPStatus.OK
    get_json_resp = get_rv.get_json()

    # Only the last PAGE_SIZE orders should be returned
    assert len(get_json_resp) == constants.PAGE_SIZE
    expected_uuids = order_uuids[-constants.PAGE_SIZE:]
    expected_uuids.reverse()  # match the sorting from newest to oldest
    for i in range(constants.PAGE_SIZE):
        assert get_json_resp[i]['uuid'] == expected_uuids[i]


@patch('orders.new_invoice')
@patch('constants.FORCE_PAYMENT', True)
def test_create_order_with_force_payment_enabled(mock_new_invoice, client):
    uuid_order1 = generate_test_order(mock_new_invoice, client)['uuid']
    uuid_order2 = generate_test_order(mock_new_invoice, client)['uuid']

    db_order1 = Order.query.filter_by(uuid=uuid_order1).first()
    db_invoice1 = db_order1.invoices[0]

    db_order2 = Order.query.filter_by(uuid=uuid_order2).first()
    db_invoice2 = db_order2.invoices[0]

    # Since FORCE_PAYMENT is set and both orders have only one invoice, both
    # orders change their statuses to paid. Furthermore, the payment triggers a
    # Tx start verification and, since the transmit queue is empty, order1
    # immediately changes to transmitting state. In contrast, order2 stays in
    # paid state as it needs to wait until the transmission of order1 finishes.
    assert db_order1.status == OrderStatus.transmitting.value
    assert db_invoice1.status == InvoiceStatus.paid.value
    assert db_invoice1.paid_at is not None

    assert db_order2.status == OrderStatus.paid.value
    assert db_invoice2.status == InvoiceStatus.paid.value
    assert db_invoice2.paid_at is not None
