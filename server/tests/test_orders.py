import pytest
import random
from datetime import timedelta
from http import HTTPStatus
from time import sleep
from unittest.mock import patch

from constants import InvoiceStatus, OrderStatus
from database import db
from models import Order
from invoice_helpers import pay_invoice
import bidding
import constants
import server

from common import new_invoice, place_order, generate_test_order


@pytest.fixture
def client():
    app = server.create_app(from_test=True)
    app.app_context().push()
    with app.test_client() as client:
        yield client
    server.teardown_app(app)


@pytest.mark.parametrize("state", ['pending', 'queued', 'sent'])
def test_get_orders_invalid_before_parameter(client, state):
    get_rv = client.get(f'/orders/{state}?before=')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?before=sometext')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?before=2021-13-11')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?before=2021.05.10')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?before=2021-05-1a0T19:51:45')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?before=2021.05.10T19:51:45')
    assert get_rv.status_code == HTTPStatus.BAD_REQUEST
    get_rv = client.get(f'/orders/{state}?before=2021-05-10T25:51:45')
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
@patch('orders.new_invoice')
@pytest.mark.parametrize("state", ['pending', 'queued', 'sent'])
def test_get_orders_before_parameter(mock_new_invoice, client, state):
    # Create PAGE_SIZE orders with the target state
    n_orders = constants.PAGE_SIZE
    n_bytes = 500
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bidding.get_min_bid(n_bytes)))
    order_uuids = []
    for i in range(n_orders):
        post_rv = place_order(client, n_bytes)
        assert post_rv.status_code == HTTPStatus.OK
        uuid = post_rv.get_json()['uuid']
        order_uuids.append(uuid)
        db_order = Order.query.filter_by(uuid=uuid).first()
        db_order.status = OrderStatus.transmitting.value if \
            state == 'queued' else OrderStatus[state].value
        db.session.commit()
        sleep(1.0)  # to have different created_at

    # Fetch orders excluding the last
    last_db_order = Order.query.filter_by(uuid=order_uuids[-1]).first()
    last_created_at = last_db_order.created_at.isoformat()

    get_rv = client.get(f'/orders/{state}?before={last_created_at}')
    assert get_rv.status_code == HTTPStatus.OK
    fetched_uuids = [order['uuid'] for order in get_rv.get_json()]

    # The last order should be filtered out by the before filter
    expected_uuids = order_uuids[:-1]
    # Expected sorting: /orders/pending endpoint sorts by the created_at
    # timestamp, /orders/queued by the bid_per_byte ratio, and /orders/sent by
    # the transmission_at timestamp.
    if (state == 'pending'):
        expected_uuids.reverse()

    assert len(fetched_uuids) == n_orders - 1
    assert fetched_uuids == expected_uuids


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

    # no limit parameter, max PAGE_SIZE should be retunred
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
    for state in ['pending', 'transmitting', 'sent', 'received']:
        order[state] = generate_test_order(mock_new_invoice,
                                           client,
                                           order_status=OrderStatus[state])

    # Request queued orders
    get_rv = client.get('/orders/queued')
    assert get_rv.status_code == HTTPStatus.OK
    queued_uuids = [order['uuid'] for order in get_rv.get_json()]

    # The expectation is that only pending and transmitting orders are returned
    assert len(queued_uuids) == 2
    assert order['pending']['uuid'] in queued_uuids
    assert order['transmitting']['uuid'] in queued_uuids
    assert order['sent']['uuid'] not in queued_uuids
    assert order['received']['uuid'] not in queued_uuids


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

    db_order = Order.query.filter_by(uuid=uuid_order1).first()
    db_invoice = db_order.invoices[0]

    # because FORCE_PAYMENT is set and this order had only 1 invoice
    # the expectation is that both the invoice and the order have the
    # paid status
    assert db_order.status == OrderStatus.paid.value
    assert db_invoice.status == InvoiceStatus.paid.value
    assert db_invoice.paid_at is not None
