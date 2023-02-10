import random
from datetime import datetime, timedelta
from http import HTTPStatus
from math import ceil, floor
from unittest.mock import patch

import pytest

from constants import InvoiceStatus, OrderStatus, ORDER_FETCH_STATES
from database import db
from models import Order, TxRetry
import constants
import server

from common import new_invoice, place_order, generate_test_order
from error import assert_error


def place_orders(client,
                 mock_new_invoice,
                 n_orders,
                 n_bytes,
                 target_state='pending',
                 channel=1,
                 admin=False):
    # target_state refers to one of the order fetching states accepted by the
    # /orders/:state endpoint. Set the target order status based on that.
    if target_state in ['queued', 'retransmitting']:
        order_status = OrderStatus.transmitting.value
    elif target_state == 'rx-pending':
        order_status = OrderStatus.sent.value
    else:
        order_status = OrderStatus[target_state].value

    order_list = []
    for i in range(n_orders):
        # Randomize the bid
        bid_per_byte = random.randint(1, 10000)
        bid = bid_per_byte * n_bytes

        # Randomize the relevant timestamps
        tstamp = datetime.utcnow() - timedelta(
            seconds=random.randint(1, 10000))

        mock_new_invoice.return_value = (True,
                                         new_invoice(1, InvoiceStatus.pending,
                                                     bid))

        post_rv = place_order(client,
                              n_bytes,
                              bid=bid,
                              channel=channel,
                              admin=admin)
        assert post_rv.status_code == HTTPStatus.OK
        uuid = post_rv.get_json()['uuid']

        # Set the status and the fields required in each status
        db_order = Order.query.filter_by(uuid=uuid).first()
        db_order.created_at = tstamp
        db_order.status = order_status
        if target_state in ['transmitting', 'confirming', 'retransmitting']:
            db_order.started_transmission_at = tstamp
        if target_state in ['sent', 'received', 'rx-pending']:
            db_order.ended_transmission_at = tstamp
        if target_state == 'retransmitting':
            new_retry_tx = TxRetry(order_id=db_order.id,
                                   region_code=0,
                                   last_attempt=tstamp)
            db.session.add(new_retry_tx)
        db.session.commit()
        order_list.append(db_order)
    return order_list


@pytest.fixture
def client(mockredis):
    app = server.create_app(from_test=True)
    app.app_context().push()
    with app.test_client() as client:
        yield client
    server.teardown_app(app)


@pytest.mark.parametrize("param", ['before', 'after'])
def test_get_orders_invalid_before_after_parameter(client, param):
    for tstamp in [
            '', '2021-13-11', '2021.05.10', '2021-05-1a0T19:51:45',
            '2021.05.10T19:51:45', '2021-05-10T25:51:45'
    ]:
        get_rv = client.get(f'/orders/pending?{param}={tstamp}')
        assert get_rv.status_code == HTTPStatus.BAD_REQUEST
        assert f'{param}' in get_rv.get_json()

    get_rv = client.get(f'/orders/pending?{param}=2021-05-10T22:51:45')
    assert get_rv.status_code == HTTPStatus.OK
    # before and before_delta together should not be allowed. Same for after
    # and after_delta.
    get_rv = client.get(
        f'/orders/pending?{param}=2021-05-10T22:51:45&{param}_delta=5')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.parametrize("param", ['before', 'after'])
def test_get_orders_invalid_before_after_delta_parameter(client, param):
    for delta in ['', 'sometext', '2021-05-10T25:51:45', '5.2']:
        get_rv = client.get(f'/orders/pending?{param}_delta={delta}')
        assert get_rv.status_code == HTTPStatus.BAD_REQUEST
        assert f'{param}_delta' in get_rv.get_json()

    get_rv = client.get(f'/orders/pending?{param}_delta=5')
    assert get_rv.status_code == HTTPStatus.OK
    # before and before_delta together should not be allowed. Same for after
    # and after_delta.
    get_rv = client.get(
        f'/orders/pending?{param}_delta=5&{param}=2021-05-10T22:51:45')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST


def test_get_orders_invalid_limit(client):
    for limit in [
            '',
            'sometext',
            '1a2',
            '-1',
            '1.2',
            constants.MAX_PAGE_SIZE + 1,
    ]:
        get_rv = client.get(f'/orders/pending?limit={limit}')
        assert get_rv.status_code == HTTPStatus.BAD_REQUEST
        assert 'limit' in get_rv.get_json()

    get_rv = client.get('/orders/pending?limit=1')
    assert get_rv.status_code == HTTPStatus.OK
    get_rv = client.get(f'/orders/pending?limit={constants.MAX_PAGE_SIZE}')
    assert get_rv.status_code == HTTPStatus.OK


def test_try_to_get_invalid_order_state(client):
    for state in ['pendiing', 'someendpoint', 'Pending']:
        get_rv = client.get(f'/orders/{state}')
        assert get_rv.status_code == HTTPStatus.NOT_FOUND


@patch('constants.PAGE_SIZE', 3)  # change PAGE_SIZE to run this test faster
@patch('orders.new_invoice')
@pytest.mark.parametrize("state", ORDER_FETCH_STATES)
def test_get_orders_date_filtering_parameters(mock_new_invoice, client, state):
    # Create PAGE_SIZE orders with random timestamps
    n_bytes = 500
    n_orders = constants.PAGE_SIZE
    order_list = place_orders(client, mock_new_invoice, n_orders, n_bytes,
                              state)
    sorted_orders = sorted(order_list,
                           key=lambda x: x.created_at,
                           reverse=True)
    order_uuids = [x.uuid for x in sorted_orders]
    order_creation_timestamps = sorted([x.created_at for x in order_list],
                                       reverse=True)

    # Fetch orders excluding the most recent
    uuid_set1 = set(order_uuids[1:])
    before = order_creation_timestamps[0].isoformat()
    get_rv = client.get(f'/orders/{state}?before={before}')
    assert get_rv.status_code == HTTPStatus.OK
    assert set([x['uuid'] for x in get_rv.get_json()]) == uuid_set1

    # Fetch orders excluding the oldest
    uuid_set2 = set(order_uuids[:-1])
    after = order_creation_timestamps[-1].isoformat()
    get_rv = client.get(f'/orders/{state}?after={after}')
    assert get_rv.status_code == HTTPStatus.OK
    assert set([x['uuid'] for x in get_rv.get_json()]) == uuid_set2

    # Fetch the two orders in the middle
    uuid_set3 = set(order_uuids[1:-1])
    get_rv = client.get(f'/orders/{state}?after={after}&before={before}')
    assert get_rv.status_code == HTTPStatus.OK
    assert set([x['uuid'] for x in get_rv.get_json()]) == uuid_set3

    # Try the same using the delta parameters

    # Fetch orders excluding the most recent
    delta_to_most_recent = datetime.utcnow() - order_creation_timestamps[0]
    before_delta = ceil(delta_to_most_recent.total_seconds()) + 1
    get_rv = client.get(f'/orders/{state}?before_delta={before_delta}')
    assert get_rv.status_code == HTTPStatus.OK
    assert set([x['uuid'] for x in get_rv.get_json()]) == uuid_set1

    # Fetch orders excluding the oldest
    delta_to_oldest = datetime.utcnow() - order_creation_timestamps[-1]
    after_delta = floor(delta_to_oldest.total_seconds()) - 1
    get_rv = client.get(f'/orders/{state}?after_delta={after_delta}')
    assert get_rv.status_code == HTTPStatus.OK
    assert set([x['uuid'] for x in get_rv.get_json()]) == uuid_set2

    # Fetch the two orders in the middle
    get_rv = client.get(f'/orders/{state}?after_delta={after_delta}&' +
                        f'before_delta={before_delta}')
    assert get_rv.status_code == HTTPStatus.OK
    assert set([x['uuid'] for x in get_rv.get_json()]) == uuid_set3


@patch('orders.new_invoice')
@pytest.mark.parametrize("state", ['pending', 'retransmitting'])
def test_get_orders_limit_parameter(mock_new_invoice, client, state):
    n_bytes = 500
    n_orders = constants.PAGE_SIZE + 1
    place_orders(client, mock_new_invoice, n_orders, n_bytes, state)

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


@patch('constants.PAGE_SIZE', 3)  # change PAGE_SIZE to run this test faster
@patch('orders.new_invoice')
@pytest.mark.parametrize("state", ORDER_FETCH_STATES)
@pytest.mark.parametrize("channel", constants.CHANNELS)
def test_get_orders_by_channel(mock_new_invoice, client, state, channel):
    n_bytes = 500
    n_orders = constants.PAGE_SIZE + 1
    place_orders(client,
                 mock_new_invoice,
                 n_orders,
                 n_bytes,
                 state,
                 channel=channel,
                 admin=True)

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
@patch('constants.PAGE_SIZE', 3)  # change PAGE_SIZE to run this test faster
def test_get_orders_paging(mock_new_invoice, client):
    # make more orders than PAGE_SIZE
    n_orders = constants.PAGE_SIZE + 2
    n_bytes = 500
    order_list = place_orders(client, mock_new_invoice, n_orders, n_bytes)
    sorted_orders = sorted(order_list,
                           key=lambda x: x.created_at,
                           reverse=True)
    order_uuids = [x.uuid for x in sorted_orders]

    # Check all orders were created
    all_orders = Order.query.filter_by(status=OrderStatus.pending.value).all()
    assert len(all_orders) == n_orders

    # Fetch the pending orders with paging
    get_rv = client.get('/orders/pending')
    assert get_rv.status_code == HTTPStatus.OK
    resp_uuids = [x['uuid'] for x in get_rv.get_json()]

    # Only the last PAGE_SIZE orders should be returned
    assert len(resp_uuids) == constants.PAGE_SIZE
    assert resp_uuids == order_uuids[:constants.PAGE_SIZE]


@patch('orders.new_invoice')
@pytest.mark.parametrize("queue", ['queued', 'sent'])
def test_get_orders_multi_state_queues(mock_new_invoice, client, queue):
    """Test queues that return orders in multiple state"""
    # Create some orders with different states
    order_dict = {}
    for state in [
            'pending', 'paid', 'transmitting', 'sent', 'received', 'confirming'
    ]:
        order_dict[state] = generate_test_order(
            mock_new_invoice, client, order_status=OrderStatus[state])
        if state in ['sent', 'received']:
            db_order = Order.query.filter_by(
                uuid=order_dict[state]['uuid']).first()
            db_order.ended_transmission_at = datetime.utcnow()
            db.session.commit()

    # Fetch the orders from the chosen queue
    get_rv = client.get(f'/orders/{queue}')
    assert get_rv.status_code == HTTPStatus.OK
    queued_uuids = [order['uuid'] for order in get_rv.get_json()]

    # Status that can be expected in the chosen queue
    expected_status = {
        'queued': ['paid', 'transmitting', 'confirming'],
        'sent': ['sent', 'received']
    }

    for state in order_dict:
        if state in expected_status[queue]:
            assert order_dict[state]['uuid'] in queued_uuids
        else:
            assert order_dict[state]['uuid'] not in queued_uuids


@patch('orders.new_invoice')
@pytest.mark.parametrize("state", ORDER_FETCH_STATES)
def test_get_orders_sorting(mock_new_invoice, client, state):
    n_bytes = 500
    n_orders = 10
    order_list = place_orders(client, mock_new_invoice, n_orders, n_bytes,
                              state)

    if state in ['pending', 'paid']:
        # sorted by created_at
        expected_sorted_orders = sorted(order_list,
                                        key=lambda x: x.created_at,
                                        reverse=True)
    elif state in ['transmitting', 'confirming', 'retransmitting']:
        # sorted by started_transmission_at
        expected_sorted_orders = sorted(
            order_list, key=lambda x: x.started_transmission_at, reverse=True)
    elif state in ['sent', 'received', 'rx-pending']:
        # sorted by ended_transmission_at
        expected_sorted_orders = sorted(order_list,
                                        key=lambda x: x.ended_transmission_at,
                                        reverse=True)
    elif state == 'queued':
        # sorted by bid_per_byte
        expected_sorted_orders = sorted(order_list,
                                        key=lambda x: x.bid_per_byte,
                                        reverse=True)

    get_rv = client.get(f'/orders/{state}')
    assert get_rv.status_code == HTTPStatus.OK
    get_json_resp = get_rv.get_json()
    assert len(get_json_resp) == n_orders
    for i in range(n_orders):
        assert get_json_resp[i]['uuid'] == expected_sorted_orders[i].uuid
        assert get_json_resp[i]['bid_per_byte'] == expected_sorted_orders[
            i].bid_per_byte


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
