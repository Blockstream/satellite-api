import io
import os
import pytest
from http import HTTPStatus
from unittest.mock import patch
from uuid import uuid4

from constants import InvoiceStatus, OrderStatus
from database import db
from error import assert_error, get_http_error_resp
from models import Invoice, Order, RxConfirmation, TxConfirmation
from order_helpers import adjust_bids, _paid_invoices_total,\
    _unpaid_invoices_total
from regions import Regions, SATELLITE_REGIONS
from utils import hmac_sha256_digest
import bidding
import constants
import server

from common import check_invoice, pay_invoice, check_upload, new_invoice,\
    place_order, generate_test_order, rnd_string, upload_test_file


@pytest.fixture
def client(mockredis):
    app = server.create_app(from_test=True)
    app.app_context().push()
    with app.test_client() as client:
        yield client
    server.teardown_app(app)


def check_received_message(order_uuid, received_message):
    path = os.path.join(constants.MSG_STORE_PATH, order_uuid)
    assert os.path.exists(path)
    with open(path, 'rb') as fd:
        sent_message = fd.read()
    assert sent_message == received_message


@patch('orders.new_invoice')
def test_file_upload(mock_new_invoice, client):
    n_bytes = 500
    bid = bidding.get_min_bid(n_bytes)
    msg = rnd_string(n_bytes)
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bid))

    rv = upload_test_file(client, msg, bid)
    assert rv.status_code == HTTPStatus.OK
    check_upload(rv.get_json()['uuid'], msg)
    check_invoice(rv.get_json()['lightning_invoice'], rv.get_json()['uuid'])


@patch('orders.new_invoice')
def test_text_msg_upload(mock_new_invoice, client):
    n_bytes = 500
    bid = bidding.get_min_bid(n_bytes)
    msg = rnd_string(n_bytes)
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bid))
    rv = client.post('/order', data={'bid': bid, 'message': msg.encode()})
    assert rv.status_code == HTTPStatus.OK
    check_upload(rv.get_json()['uuid'], msg)
    check_invoice(rv.get_json()['lightning_invoice'], rv.get_json()['uuid'])


def test_uploaded_file_too_small(client):
    n_bytes = 0
    rv = place_order(client, n_bytes)
    assert_error(rv.get_json(), 'MESSAGE_FILE_TOO_SMALL')
    assert rv.status_code == HTTPStatus.BAD_REQUEST


def test_uploaded_file_too_large(client):
    n_bytes = constants.DEFAULT_MAX_MESSAGE_SIZE + 1
    rv = place_order(client, n_bytes)
    assert_error(rv.get_json(), 'MESSAGE_FILE_TOO_LARGE')
    assert rv.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE

    # The limit is different per channel. For instance, the default size would
    # work on the btc-src channel.
    rv = place_order(client,
                     n_bytes,
                     channel=constants.BTC_SRC_CHANNEL,
                     admin=True)
    assert rv.status_code == HTTPStatus.OK

    n_bytes = constants.CHANNEL_INFO[
        constants.BTC_SRC_CHANNEL].max_msg_size + 1
    rv = place_order(client, n_bytes)
    assert_error(rv.get_json(), 'MESSAGE_FILE_TOO_LARGE')
    assert rv.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE


@patch('orders.new_invoice')
def test_uploaded_file_max_size(mock_new_invoice, client):
    n_bytes = constants.DEFAULT_MAX_MESSAGE_SIZE
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bidding.get_min_bid(n_bytes)))
    rv = place_order(client, n_bytes)
    assert rv.status_code == HTTPStatus.OK


def test_uploaded_text_msg_too_large(client):
    n_bytes = constants.MAX_TEXT_MSG_LEN + 1
    bid = bidding.get_min_bid(n_bytes)
    msg = rnd_string(n_bytes)
    rv = client.post('/order', data={'bid': bid, 'message': msg.encode()})
    assert rv.status_code == HTTPStatus.BAD_REQUEST


def test_post_order_invalid_channel(client):
    n_bytes = 10
    bid = bidding.get_min_bid(n_bytes)
    msg = rnd_string(n_bytes)
    rv = client.post('/order',
                     data={
                         'bid': bid,
                         'message': msg.encode(),
                         'channel': 10
                     })
    assert rv.status_code == HTTPStatus.BAD_REQUEST
    assert 'channel' in rv.get_json()
    assert "Must be one of" in rv.get_json()['channel'][0]


@patch('orders.new_invoice')
def test_uploaded_text_msg_max_size(mock_new_invoice, client):
    n_bytes = constants.MAX_TEXT_MSG_LEN
    bid = bidding.get_min_bid(n_bytes)
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bid))
    bid = bidding.get_min_bid(n_bytes)
    msg = rnd_string(n_bytes)
    rv = client.post('/order', data={'bid': bid, 'message': msg.encode()})
    assert rv.status_code == HTTPStatus.OK


@patch('orders.new_invoice')
def test_both_msg_and_file_provided(mock_new_invoice, client):
    n_bytes = 500
    bid = bidding.get_min_bid(n_bytes)
    msg = rnd_string(n_bytes)
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bid))
    rv = client.post('/order',
                     data={
                         'bid': bid,
                         'message': msg.encode(),
                         'file': (io.BytesIO(msg.encode()), 'testfile')
                     })
    assert rv.status_code == HTTPStatus.BAD_REQUEST


def test_negative_bid(client):
    n_bytes = 500
    bid = -1
    msg = rnd_string(n_bytes)
    rv = upload_test_file(client, msg, bid)
    assert 'bid' in rv.get_json()
    assert rv.get_json()['bid'][0] == 'Must be greater than or equal to 0.'
    assert rv.status_code == HTTPStatus.BAD_REQUEST


def test_bid_too_low(client):
    n_bytes = 1000
    bid = 1051
    msg = rnd_string(n_bytes)
    rv = upload_test_file(client, msg, bid)
    assert_error(rv.get_json(), 'BID_TOO_SMALL')
    assert rv.status_code == HTTPStatus.BAD_REQUEST


def test_order_without_message(client):
    n_bytes = 500
    bid = bidding.get_min_bid(n_bytes)
    rv = client.post('/order', data={'bid': bid})
    assert_error(rv.get_json(), 'MESSAGE_MISSING')
    assert rv.status_code == HTTPStatus.BAD_REQUEST


@patch('orders.new_invoice')
def test_invoice_generation_failure(mock_new_invoice, client):
    mock_new_invoice.return_value =\
        (False,
         get_http_error_resp('LIGHTNING_CHARGE_INVOICE_ERROR'))
    n_bytes = 500
    rv = place_order(client, n_bytes)
    assert rv.status_code == HTTPStatus.BAD_REQUEST
    mock_new_invoice.return_value =\
        (False,
         get_http_error_resp(
             'LIGHTNING_CHARGE_WEBHOOK_REGISTRATION_ERROR'
             ))
    rv = place_order(client, n_bytes)
    assert rv.status_code == HTTPStatus.BAD_REQUEST


@patch('orders.new_invoice')
def test_get_order(mock_new_invoice, client):
    json_response = generate_test_order(mock_new_invoice, client)
    uuid = json_response['uuid']
    auth_token = json_response['auth_token']

    get_rv = client.get(f'/order/{uuid}', headers={'X-Auth-Token': auth_token})
    get_json_resp = get_rv.get_json()
    assert get_rv.status_code == HTTPStatus.OK
    assert get_json_resp['uuid'] == uuid


@patch('orders.new_invoice')
def test_get_order_auth_token_as_form_param(mock_new_invoice, client):
    json_response = generate_test_order(mock_new_invoice, client)
    uuid = json_response['uuid']
    auth_token = json_response['auth_token']

    get_rv = client.get(f'/order/{uuid}', data={'auth_token': auth_token})
    get_json_resp = get_rv.get_json()
    assert get_rv.status_code == HTTPStatus.OK
    assert get_json_resp['uuid'] == uuid


@patch('orders.new_invoice')
def test_get_order_auth_token_as_query_param(mock_new_invoice, client):
    json_response = generate_test_order(mock_new_invoice, client)
    uuid = json_response['uuid']
    auth_token = json_response['auth_token']

    get_rv = client.get(f'/order/{uuid}?auth_token={auth_token}')
    get_json_resp = get_rv.get_json()
    assert get_rv.status_code == HTTPStatus.OK
    assert get_json_resp['uuid'] == uuid


def test_get_nonexistent_order(client):
    uuid = str(uuid4())
    rv = client.get(f'/order/{uuid}',
                    headers={'X-Auth-Token': 'test-auth-token'})
    assert_error(rv.get_json(), 'ORDER_NOT_FOUND')
    assert rv.status_code == HTTPStatus.NOT_FOUND


@patch('orders.new_invoice')
def test_get_order_wrong_auth_token(mock_new_invoice, client):
    uuid = generate_test_order(mock_new_invoice, client)['uuid']

    get_rv = client.get(f'/order/{uuid}',
                        headers={'X-Auth-Token': 'wrong-auth-token'})
    assert_error(get_rv.get_json(), 'INVALID_AUTH_TOKEN')
    assert get_rv.status_code == HTTPStatus.UNAUTHORIZED


@patch('orders.new_invoice')
def test_get_order_missing_auth_token(mock_new_invoice, client):
    uuid = generate_test_order(mock_new_invoice, client)['uuid']

    get_rv = client.get(f'/order/{uuid}')
    assert_error(get_rv.get_json(), 'INVALID_AUTH_TOKEN')
    assert get_rv.status_code == HTTPStatus.UNAUTHORIZED


@patch('orders.new_invoice')
def test_get_admin_order(mock_new_invoice, client):
    # Post order on a channel that forbids users from fetching messages
    json_response = generate_test_order(mock_new_invoice,
                                        client,
                                        channel=constants.AUTH_CHANNEL,
                                        admin=True)
    uuid = json_response['uuid']
    auth_token = json_response['auth_token']

    # Getting through the normal route should fail
    get_rv = client.get(f'/order/{uuid}', headers={'X-Auth-Token': auth_token})
    assert get_rv.status_code == HTTPStatus.UNAUTHORIZED
    assert_error(get_rv.get_json(), 'ORDER_CHANNEL_UNAUTHORIZED_OP')

    # Getting through the admin route should work
    get_rv = client.get(f'/admin/order/{uuid}',
                        headers={'X-Auth-Token': auth_token})
    get_json_resp = get_rv.get_json()
    assert get_rv.status_code == HTTPStatus.OK
    assert get_json_resp['uuid'] == uuid


def test_adjust_bids(client):
    # if the values like bid, unpaid_bid, bid_per_byte are wrong or become
    # obsolete due to changes in the invoices, the adjust_bids function should
    # be able to fix them all
    n_bytes = 1000
    paid_bid = 1000
    unpaid_bid = 10000
    order = Order(id=1,
                  uuid='a-b-c',
                  bid=123,
                  message_size=n_bytes,
                  bid_per_byte=56.0,
                  message_digest='abcd',
                  status=OrderStatus.pending.value,
                  unpaid_bid=2345,
                  invoices=[
                      new_invoice(1, InvoiceStatus.pending,
                                  int(0.4 * unpaid_bid)),
                      new_invoice(1, InvoiceStatus.pending,
                                  int(0.6 * unpaid_bid)),
                      new_invoice(1, InvoiceStatus.paid, int(0.3 * paid_bid)),
                      new_invoice(1, InvoiceStatus.paid, int(0.7 * paid_bid))
                  ])
    assert _paid_invoices_total(order) == paid_bid
    assert _unpaid_invoices_total(order) == unpaid_bid
    adjust_bids(order)
    assert order.bid == paid_bid
    assert order.unpaid_bid == unpaid_bid
    expected_bid_per_byte = paid_bid / (n_bytes + 52)  # w/ 52 overhead bytes
    assert order.bid_per_byte == expected_bid_per_byte


@patch('orders.new_invoice')
def test_negative_bid_increase_error(mock_new_invoice, client):
    initial_bid = 1000
    json_response = generate_test_order(mock_new_invoice,
                                        client,
                                        bid=initial_bid)
    uuid = json_response['uuid']
    auth_token = json_response['auth_token']

    # Bump the bid with a negative value
    bump_rv = client.post(f'/order/{uuid}/bump',
                          data={
                              'bid_increase': -1,
                          },
                          headers={'X-Auth-Token': auth_token})
    assert bump_rv.status_code == HTTPStatus.BAD_REQUEST


@patch('orders.new_invoice')
def test_bump_order(mock_new_invoice, client):
    initial_bid = 1000
    json_response = generate_test_order(mock_new_invoice,
                                        client,
                                        bid=initial_bid)
    uuid = json_response['uuid']
    auth_token = json_response['auth_token']

    get_rv = client.get(f'/order/{uuid}', headers={'X-Auth-Token': auth_token})
    assert get_rv.status_code == HTTPStatus.OK
    get_json_resp = get_rv.get_json()
    assert get_json_resp['unpaid_bid'] == initial_bid
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert len(db_order.invoices) == 1

    # Bump the bid on the existing order
    bid_increase = 2500
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bid_increase))
    bump_rv = client.post(f'/order/{uuid}/bump',
                          data={
                              'bid_increase': bid_increase,
                          },
                          headers={'X-Auth-Token': auth_token})
    assert bump_rv.status_code == HTTPStatus.OK

    # Get the order and check if the bid was bumped successfully
    get_rv = client.get(f'/order/{uuid}', headers={'X-Auth-Token': auth_token})
    assert get_rv.status_code == HTTPStatus.OK
    get_json_resp = get_rv.get_json()
    assert get_json_resp['unpaid_bid'] == initial_bid + bid_increase
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert len(db_order.invoices) == 2

    # If a bump request fails, the order should stay untouched
    second_bid_increase = 3000
    mock_new_invoice.return_value = \
        (False,
         get_http_error_resp('LIGHTNING_CHARGE_INVOICE_ERROR'))
    bump_rv = client.post(f'/order/{uuid}/bump',
                          data={
                              'bid_increase': second_bid_increase,
                          },
                          headers={'X-Auth-Token': auth_token})
    assert bump_rv.status_code == HTTPStatus.BAD_REQUEST

    # Get the order and verify the second bid increase (which failed) was
    # completely ignored
    get_rv = client.get(f'/order/{uuid}', headers={'X-Auth-Token': auth_token})
    assert get_rv.status_code == HTTPStatus.OK
    get_json_resp = get_rv.get_json()
    assert get_json_resp['unpaid_bid'] == initial_bid + bid_increase
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert len(db_order.invoices) == 2


@patch('orders.new_invoice')
def test_bump_transmitted_order(mock_new_invoice, client):
    initial_bid = 1000
    json_response = generate_test_order(mock_new_invoice,
                                        client,
                                        bid=initial_bid)
    uuid = json_response['uuid']
    auth_token = json_response['auth_token']
    db_order = Order.query.filter_by(uuid=uuid).first()
    pay_invoice(db_order.invoices[0], client)
    db.session.commit()

    get_rv = client.get(f'/order/{uuid}', headers={'X-Auth-Token': auth_token})
    assert get_rv.status_code == HTTPStatus.OK
    get_json_resp = get_rv.get_json()
    assert get_json_resp['unpaid_bid'] == 0
    assert get_json_resp['bid'] == initial_bid
    assert get_json_resp['status'] == OrderStatus.transmitting.name

    # Since the order is already in transmitting state, a bump request should
    # return error
    bid_increase = 2500
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bid_increase))
    bump_rv = client.post(f'/order/{uuid}/bump',
                          data={
                              'bid_increase': bid_increase,
                          },
                          headers={'X-Auth-Token': auth_token})
    assert bump_rv.status_code == HTTPStatus.BAD_REQUEST
    assert_error(bump_rv.get_json(), 'ORDER_BUMP_ERROR')


@patch('orders.new_invoice')
def test_bump_non_paid_order(mock_new_invoice, client):
    # Send order over the gossip channel, which is not paid.
    initial_bid = 1000
    json_response = generate_test_order(mock_new_invoice,
                                        client,
                                        bid=initial_bid,
                                        channel=constants.GOSSIP_CHANNEL,
                                        admin=True)
    uuid = json_response['uuid']
    auth_token = json_response['auth_token']

    # Since the order is not paid, a bump request should not be authorized
    bid_increase = 2500
    bump_rv = client.post(f'/order/{uuid}/bump',
                          data={
                              'bid_increase': bid_increase,
                          },
                          headers={'X-Auth-Token': auth_token})
    assert bump_rv.status_code == HTTPStatus.UNAUTHORIZED
    assert_error(bump_rv.get_json(), 'ORDER_CHANNEL_UNAUTHORIZED_OP')


@patch('orders.new_invoice')
def test_cancel_order(mock_new_invoice, client):
    bid = 1000
    json_response = generate_test_order(mock_new_invoice, client, bid=bid)
    uuid = json_response['uuid']
    auth_token = json_response['auth_token']

    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.pending.value
    assert db_order.cancelled_at is None

    # Only pending and paid orders can be cancelled
    for status in OrderStatus:
        db_order.status = status.value
        db.session.commit()
        if status in [OrderStatus.paid, OrderStatus.pending]:
            delete_rv = client.delete(f'/order/{uuid}',
                                      headers={'X-Auth-Token': auth_token})
            assert delete_rv.status_code == HTTPStatus.OK
        else:
            delete_rv = client.delete(f'/order/{uuid}',
                                      headers={'X-Auth-Token': auth_token})
            assert delete_rv.status_code == HTTPStatus.BAD_REQUEST
            assert_error(delete_rv.get_json(), 'ORDER_CANCELLATION_ERROR')


@patch('orders.new_invoice')
def test_cancel_order_twice(mock_new_invoice, client):
    bid = 1000
    json_response = generate_test_order(mock_new_invoice, client, bid=bid)
    uuid = json_response['uuid']
    auth_token = json_response['auth_token']

    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.pending.value
    assert db_order.cancelled_at is None
    message_path = os.path.join(constants.MSG_STORE_PATH, uuid)
    assert os.path.exists(message_path)

    # Cancel the order
    delete_rv = client.delete(f'/order/{uuid}',
                              headers={'X-Auth-Token': auth_token})
    assert delete_rv.status_code == HTTPStatus.OK
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.cancelled.value
    assert db_order.cancelled_at is not None
    assert not os.path.exists(message_path)

    # Try to cancel the order again
    delete_rv = client.delete(f'/order/{uuid}',
                              headers={'X-Auth-Token': auth_token})
    assert delete_rv.status_code == HTTPStatus.BAD_REQUEST
    assert_error(delete_rv.get_json(), 'ORDER_CANCELLATION_ERROR')


def test_cancel_non_existing_order(client):
    delete_rv = client.delete('/order/13245',
                              headers={'X-Auth-Token': 'token'})
    assert delete_rv.status_code == HTTPStatus.NOT_FOUND
    assert_error(delete_rv.get_json(), 'ORDER_NOT_FOUND')


@patch('orders.new_invoice')
def test_cancel_order_unauthorized_channel_op(mock_new_invoice, client):
    # Place order on a channel that forbids uses from deleting orders.
    bid = 1000
    json_response = generate_test_order(mock_new_invoice,
                                        client,
                                        bid=bid,
                                        channel=constants.GOSSIP_CHANNEL,
                                        admin=True)
    uuid = json_response['uuid']
    auth_token = json_response['auth_token']

    # Deleting through the regular user endpoint should fail
    delete_rv = client.delete(f'/order/{uuid}',
                              headers={'X-Auth-Token': auth_token})
    assert delete_rv.status_code == HTTPStatus.UNAUTHORIZED
    assert_error(delete_rv.get_json(), 'ORDER_CHANNEL_UNAUTHORIZED_OP')

    # Deleting through the admin endpoint should work (i.e., won't return
    # unauthorized operation)
    delete_rv = client.delete(f'/admin/order/{uuid}',
                              headers={'X-Auth-Token': auth_token})
    # In this case, it hits a cancellation error because the order is already
    # in transmitting state, given that the gossip channel is auto-paid.
    assert delete_rv.status_code == HTTPStatus.BAD_REQUEST
    assert_error(delete_rv.get_json(), 'ORDER_CANCELLATION_ERROR')
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.transmitting.value
    assert db_order.cancelled_at is None


def test_get_sent_message_for_nonexisting_uuid(client):
    # Try to get message for a non existing uuid
    rv = client.get('/order/some-uuid/sent_message')
    assert rv.status_code == HTTPStatus.NOT_FOUND
    assert_error(rv.get_json(), 'ORDER_NOT_FOUND')


@patch('orders.new_invoice')
def test_get_sent_message_for_pending_order(mock_new_invoice, client):
    uuid = generate_test_order(mock_new_invoice, client)['uuid']
    # The test order has pending status. Hence, fetching via the
    # /order/{uuid}/sent_message endpoint should fail. Only "sent" and
    # "transmitting" orders can be requested.
    rv = client.get(f'/order/{uuid}/sent_message')
    assert rv.status_code == HTTPStatus.NOT_FOUND
    assert_error(rv.get_json(), 'ORDER_NOT_FOUND')


@patch('orders.new_invoice')
@pytest.mark.parametrize("status",
                         [OrderStatus.sent, OrderStatus.transmitting])
def test_get_sent_message_from_uuid(mock_new_invoice, client, status):
    uuid = generate_test_order(mock_new_invoice, client,
                               order_status=status)['uuid']
    rv = client.get(f'/order/{uuid}/sent_message')
    assert rv.status_code == HTTPStatus.OK
    received_message = rv.data
    check_received_message(uuid, received_message)


def test_get_sent_message_for_nonexisting_seq_number(client):
    # Try to get message for a non existing seq number
    rv = client.get('/message/1')
    assert rv.status_code == HTTPStatus.NOT_FOUND
    assert_error(rv.get_json(), 'SEQUENCE_NUMBER_NOT_FOUND')


@patch('orders.new_invoice')
def test_get_sent_message_by_seq_number_for_paid_order(mock_new_invoice,
                                                       client):
    uuid = generate_test_order(mock_new_invoice, client)['uuid']
    db_order = Order.query.filter_by(uuid=uuid).first()
    pay_invoice(db_order.invoices[0], client)
    db.session.commit()

    # Because the invoice was paid, the order should go immediately into
    # transmitting state and be assigned with sequence number 1.
    rv = client.get('/message/1')
    assert rv.status_code == HTTPStatus.OK
    received_message = rv.data
    check_received_message(uuid, received_message)


@patch('orders.new_invoice')
@pytest.mark.parametrize(
    "status",
    [OrderStatus.sent, OrderStatus.received, OrderStatus.transmitting])
def test_get_sent_message_by_seq_number(mock_new_invoice, client, status):
    uuid = generate_test_order(mock_new_invoice,
                               client,
                               order_status=status,
                               tx_seq_num=1)['uuid']

    # Get order's sent message by seq number
    rv = client.get('/message/1')
    assert rv.status_code == HTTPStatus.OK
    received_message = rv.data
    check_received_message(uuid, received_message)


@patch('orders.new_invoice')
def test_get_sent_message_by_seq_number_unauthorized_channel_op(
        mock_new_invoice, client):
    # Create an order on the auth channel, which forbids GET requests from
    # users. Make sure those requests fail. And use the /admin/order endpoint
    # when POSTing the order.
    uuid = generate_test_order(mock_new_invoice,
                               client,
                               order_status=OrderStatus.sent,
                               tx_seq_num=1,
                               channel=constants.AUTH_CHANNEL,
                               admin=True)['uuid']

    # Reading by sequence number via the regular route should fail
    rv = client.get('/message/1')
    assert rv.status_code == HTTPStatus.UNAUTHORIZED
    assert_error(rv.get_json(), 'ORDER_CHANNEL_UNAUTHORIZED_OP')

    # Reading by sequence number via the admin route should fail
    rv = client.get('/admin/message/1')
    assert rv.status_code == HTTPStatus.OK
    received_message = rv.data
    check_received_message(uuid, received_message)


@patch('orders.new_invoice')
@pytest.mark.parametrize("channel", constants.CHANNELS)
def test_get_sent_message_admin(mock_new_invoice, client, channel):
    # the admin should be able to get messages from any channel
    uuid = generate_test_order(mock_new_invoice,
                               client,
                               order_status=OrderStatus.sent,
                               tx_seq_num=1,
                               channel=channel,
                               admin=True)['uuid']

    rv = client.get(f'/admin/message/1?channel={channel}')
    assert rv.status_code == HTTPStatus.OK
    received_message = rv.data
    check_received_message(uuid, received_message)


@patch('orders.new_invoice')
@pytest.mark.parametrize("channel", [
    constants.GOSSIP_CHANNEL, constants.BTC_SRC_CHANNEL, constants.AUTH_CHANNEL
])
def test_post_order_unauthorized_channel(mock_new_invoice, client, channel):
    # users are not authorized to post to some channels
    n_bytes = 500
    bid = bidding.get_min_bid(n_bytes)
    msg = rnd_string(n_bytes)
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bid))
    rv = client.post('/order',
                     data={
                         'bid': bid,
                         'message': msg.encode(),
                         'channel': channel
                     })
    assert rv.status_code == HTTPStatus.UNAUTHORIZED
    assert_error(rv.get_json(), 'ORDER_CHANNEL_UNAUTHORIZED_OP')


@patch('orders.new_invoice')
@pytest.mark.parametrize("channel", constants.CHANNELS)
def test_post_order_admin(mock_new_invoice, client, channel):
    # the admin should be allowed to POST messages to any channel
    n_bytes = 500
    bid = bidding.get_min_bid(n_bytes)
    msg = rnd_string(n_bytes)
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bid))
    rv = client.post('/admin/order',
                     data={
                         'bid': bid,
                         'message': msg.encode(),
                         'channel': channel
                     })
    assert rv.status_code == HTTPStatus.OK
    check_upload(rv.get_json()['uuid'], msg)


@patch('orders.new_invoice')
def test_confirm_tx_missing_or_invalid_param(mock_new_invoice, client):
    post_rv = client.post('/order/tx/1')
    assert post_rv.status_code == HTTPStatus.BAD_REQUEST
    post_rv = client.post('/order/tx/1', data={'regions': 'a'})
    assert post_rv.status_code == HTTPStatus.BAD_REQUEST
    post_rv = client.post('/order/tx/1', data={'regions': 1})
    assert post_rv.status_code == HTTPStatus.BAD_REQUEST
    # Confirm tx of a non existing sequence number
    post_rv = client.post('/order/tx/2', data={"regions": [[1]]})
    assert post_rv.status_code == HTTPStatus.NOT_FOUND
    assert_error(post_rv.get_json(), 'SEQUENCE_NUMBER_NOT_FOUND')
    # Create a test order but confirm Tx for an invalid region
    generate_test_order(mock_new_invoice, client, tx_seq_num=1)
    post_rv = client.post('/order/tx/1', data={'regions': [[20, 1]]})
    assert post_rv.status_code == HTTPStatus.BAD_REQUEST


@patch('orders.new_invoice')
def test_confirm_tx(mock_new_invoice, client):
    uuid = generate_test_order(mock_new_invoice, client, tx_seq_num=1)['uuid']
    db_order = Order.query.filter_by(uuid=uuid).first()

    # Confirm tx for a single region
    post_rv = client.post('/order/tx/1',
                          data={'regions': [[Regions.t11n_afr.value]]})
    assert post_rv.status_code == HTTPStatus.OK
    db_tx_confirmation = TxConfirmation.query.filter_by(
        order_id=db_order.id).all()
    assert len(db_tx_confirmation) == 1
    assert db_tx_confirmation[0].region_id == SATELLITE_REGIONS[
        Regions.t11n_afr]['id']

    # Confirm tx for multiple regions
    post_rv = client.post(
        '/order/tx/1',
        data={
            'regions':
            [[Regions.g18.value, Regions.e113.value, Regions.t11n_afr.value]]
        })
    assert post_rv.status_code == HTTPStatus.OK
    db_tx_confirmation = TxConfirmation.query.filter_by(
        order_id=db_order.id).order_by(TxConfirmation.region_id).all()
    assert len(db_tx_confirmation) == 3
    assert db_tx_confirmation[0].region_id == SATELLITE_REGIONS[
        Regions.g18]['id']
    assert db_tx_confirmation[1].region_id == SATELLITE_REGIONS[
        Regions.e113]['id']
    assert db_tx_confirmation[2].region_id == SATELLITE_REGIONS[
        Regions.t11n_afr]['id']


@patch('orders.new_invoice')
def test_confirm_rx_missing_or_invalid_param(mock_new_invoice, client):
    post_rv = client.post('/order/rx/1')
    assert post_rv.status_code == HTTPStatus.BAD_REQUEST
    post_rv = client.post('/order/rx/1', data={'region': 'a'})
    assert post_rv.status_code == HTTPStatus.BAD_REQUEST
    post_rv = client.post('/order/rx/1', data={'regions': [[1, 2]]})
    assert post_rv.status_code == HTTPStatus.BAD_REQUEST
    # Confirm rx of a non existing sequence number
    post_rv = client.post('/order/rx/2', data={"region": 1})
    assert post_rv.status_code == HTTPStatus.NOT_FOUND
    assert_error(post_rv.get_json(), 'SEQUENCE_NUMBER_NOT_FOUND')
    # Create a test order but confirm Rx for an invalid region
    generate_test_order(mock_new_invoice, client, tx_seq_num=1)
    post_rv = client.post('/order/rx/1', data={'region': 20})
    assert post_rv.status_code == HTTPStatus.BAD_REQUEST


@patch('orders.new_invoice')
def test_confirm_rx(mock_new_invoice, client):
    uuid = generate_test_order(mock_new_invoice, client, tx_seq_num=1)['uuid']
    db_order = Order.query.filter_by(uuid=uuid).first()

    post_rv = client.post('/order/rx/1', data={'region': Regions.g18.value})
    assert post_rv.status_code == HTTPStatus.OK
    db_rx_confirmation = RxConfirmation.query.filter_by(
        order_id=db_order.id).all()
    assert len(db_rx_confirmation) == 1
    assert db_rx_confirmation[0].region_id == SATELLITE_REGIONS[
        Regions.g18]['id']


@patch('orders.new_invoice')
@pytest.mark.parametrize(
    "tx_regions",
    [[Regions.g18.value], [Regions.g18.value, Regions.e113.value],
     [
         Regions.g18.value, Regions.e113.value, Regions.t11n_afr.value,
         Regions.t11n_eu.value, Regions.t18v_c.value
     ],
     [
         Regions.g18.value, Regions.e113.value, Regions.t11n_afr.value,
         Regions.t11n_eu.value, Regions.t18v_c.value, Regions.t18v_c.value
     ]])
@pytest.mark.parametrize(
    "rx_regions",
    [[Regions.g18.value], [Regions.g18.value, Regions.e113.value],
     [Regions.g18.value, Regions.e113.value, Regions.t18v_c.value],
     [
         Regions.g18.value, Regions.e113.value, Regions.t18v_c.value,
         Regions.t18v_c.value
     ]])
def test_sent_or_received_criteria_met_inadequate_regions(
        mock_new_invoice, client, tx_regions, rx_regions):
    uuid = generate_test_order(mock_new_invoice,
                               client,
                               order_status=OrderStatus.transmitting,
                               tx_seq_num=1)['uuid']

    # Confirm tx
    post_rv = client.post('/order/tx/1', data={'regions': [tx_regions]})
    assert post_rv.status_code == HTTPStatus.OK

    # Confirm rx
    for region in rx_regions:
        post_rv = client.post('/order/rx/1', data={'region': region})
        assert post_rv.status_code == HTTPStatus.OK

    # The order status should not change to sent nor received because not
    # enough regions have confirmed tx/rx
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.confirming.value


@patch('orders.new_invoice')
def test_sent_or_received_criteria_met_for_unsent_order(
        mock_new_invoice, client):
    uuid = generate_test_order(mock_new_invoice, client, tx_seq_num=1)['uuid']
    # Confirm tx for all 6 regions
    post_rv = client.post('/order/tx/1',
                          data={'regions': [[e.value for e in Regions]]})
    assert post_rv.status_code == HTTPStatus.OK

    # Confirm rx for all regions except africa and europe
    for region in [
            Regions.g18.value, Regions.e113.value, Regions.t18v_c.value,
            Regions.t18v_ku.value
    ]:
        post_rv = client.post('/order/rx/1', data={'region': region})
        assert post_rv.status_code == HTTPStatus.OK

    # Although all the required Tx/Rx confirmations are available, the order
    # still cannot change to "received" state, as that requires the order to be
    # in "sent" state before. The test order is still in "pending" state.
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.pending.value


@patch('orders.new_invoice')
def test_sent_or_received_criteria_met_successfully(mock_new_invoice, client):
    uuid = generate_test_order(mock_new_invoice,
                               client,
                               order_status=OrderStatus.transmitting,
                               tx_seq_num=1)['uuid']

    # Confirm tx for all 6 regions
    post_rv = client.post('/order/tx/1',
                          data={'regions': [[e.value for e in Regions]]})
    assert post_rv.status_code == HTTPStatus.OK
    # Order's status should change to sent
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.sent.value

    # Confirm rx for all regions except africa and europe
    for region in [
            Regions.g18.value, Regions.e113.value, Regions.t18v_c.value,
            Regions.t18v_ku.value
    ]:
        post_rv = client.post('/order/rx/1', data={'region': region})
        assert post_rv.status_code == HTTPStatus.OK

    # Order's status should change to received
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.received.value

    # Synthesized rx_confirmations for africa and europe should be created
    for region in [Regions.t11n_afr, Regions.t11n_eu]:
        db_rx_confirmation = RxConfirmation.query.filter_by(
            order_id=db_order.id).filter_by(
                region_id=SATELLITE_REGIONS[region]['id']).all()
        assert len(db_rx_confirmation) == 1
        assert db_rx_confirmation[0].presumed


@patch('orders.new_invoice')
def test_confirm_tx_repeated_regions(mock_new_invoice, client):
    uuid = generate_test_order(mock_new_invoice, client, tx_seq_num=1)['uuid']
    db_order1 = Order.query.filter_by(uuid=uuid).first()

    uuid = generate_test_order(mock_new_invoice, client, tx_seq_num=2)['uuid']
    db_order2 = Order.query.filter_by(uuid=uuid).first()

    # Confirm tx for a single region
    post_rv = client.post('/order/tx/1',
                          data={'regions': [[Regions.t11n_afr.value]]})
    assert post_rv.status_code == HTTPStatus.OK
    db_tx_confirmation = TxConfirmation.query.filter_by(
        order_id=db_order1.id).all()
    assert len(db_tx_confirmation) == 1

    # Re-Confirm tx for the same region
    post_rv = client.post('/order/tx/1',
                          data={'regions': [[Regions.t11n_afr.value]]})
    assert post_rv.status_code == HTTPStatus.OK
    db_tx_confirmation = TxConfirmation.query.filter_by(
        order_id=db_order1.id).all()
    assert len(db_tx_confirmation) == 1

    # Confirm tx for multiple regions, including t11n_afr again
    post_rv = client.post(
        '/order/tx/1',
        data={
            'regions':
            [[Regions.g18.value, Regions.t18v_c.value, Regions.t11n_afr.value]]
        })
    assert post_rv.status_code == HTTPStatus.OK
    db_tx_confirmation = TxConfirmation.query.filter_by(
        order_id=db_order1.id).all()
    assert len(db_tx_confirmation) == 3

    # Confirm tx for multiple regions, different order_id
    post_rv = client.post('/order/tx/2',
                          data={
                              'regions': [[
                                  Regions.t11n_eu.value, Regions.t18v_ku.value,
                                  Regions.t18v_ku.value
                              ]]
                          })
    assert post_rv.status_code == HTTPStatus.OK
    db_tx_confirmation = TxConfirmation.query.filter_by(
        order_id=db_order2.id).all()
    assert len(db_tx_confirmation) == 2


@patch('orders.new_invoice')
def test_confirm_rx_repeated_regions(mock_new_invoice, client):
    uuid = generate_test_order(mock_new_invoice, client, tx_seq_num=1)['uuid']
    db_order1 = Order.query.filter_by(uuid=uuid).first()

    uuid = generate_test_order(mock_new_invoice, client, tx_seq_num=2)['uuid']
    db_order2 = Order.query.filter_by(uuid=uuid).first()

    # Confirm rx for a region
    post_rv = client.post('/order/rx/1', data={'region': Regions.g18.value})
    assert post_rv.status_code == HTTPStatus.OK
    db_rx_confirmation = RxConfirmation.query.filter_by(
        order_id=db_order1.id).all()
    assert len(db_rx_confirmation) == 1

    # Re-Confirm rx for the same region
    post_rv = client.post('/order/rx/1', data={'region': Regions.g18.value})
    assert post_rv.status_code == HTTPStatus.OK
    db_rx_confirmation = RxConfirmation.query.filter_by(
        order_id=db_order1.id).all()
    assert len(db_rx_confirmation) == 1

    # Confirm rx for the same region, different order_id
    post_rv = client.post('/order/rx/2', data={'region': Regions.g18.value})
    assert post_rv.status_code == HTTPStatus.OK
    db_rx_confirmation = RxConfirmation.query.filter_by(
        order_id=db_order2.id).all()
    assert len(db_rx_confirmation) == 1


@patch('orders.new_invoice')
@pytest.mark.parametrize("status", [
    OrderStatus.transmitting, OrderStatus.sent, OrderStatus.received,
    OrderStatus.cancelled, OrderStatus.expired
])
def test_try_to_pay_a_non_pending_order(mock_new_invoice, client, status):
    n_bytes = 500
    invoice = new_invoice(1, InvoiceStatus.pending,
                          bidding.get_min_bid(n_bytes))
    mock_new_invoice.return_value = (True, invoice)
    post_rv = place_order(client, n_bytes)
    assert post_rv.status_code == HTTPStatus.OK
    uuid_order = post_rv.get_json()['uuid']
    db_order = Order.query.filter_by(uuid=uuid_order).first()
    db_order.status = status.value
    db.session.commit()

    charged_auth_token = hmac_sha256_digest(constants.LIGHTNING_WEBHOOK_KEY,
                                            invoice.lid)
    rv = client.post(f'/callback/{invoice.lid}/{charged_auth_token}')
    assert rv.status_code == HTTPStatus.OK

    # Refetch the order and the invoice from the database.
    # The expectation is that invoice changes its status to paid because
    # it had the pending status, but order keeps its current status.
    db_invoice = Invoice.query.filter_by(lid=invoice.lid).first()
    db_order = Order.query.filter_by(uuid=uuid_order).first()
    assert db_invoice.status == InvoiceStatus.paid.value
    assert db_order.status == status.value
    assert db_invoice.paid_at is not None


@patch('orders.new_invoice')
def test_bump_non_existing_order(mock_new_invoice, client):
    bid_increase = 2500
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bid_increase))
    bump_rv = client.post('/order/12345/bump',
                          data={
                              'bid_increase': bid_increase,
                          },
                          headers={'X-Auth-Token': "non-existing-token"})
    assert bump_rv.status_code == HTTPStatus.NOT_FOUND
    assert_error(bump_rv.get_json(), 'ORDER_NOT_FOUND')


@patch('orders.new_invoice')
def test_create_order_with_invalid_region(mock_new_invoice, client):
    n_bytes = 500
    bid = bidding.get_min_bid(n_bytes)
    msg = rnd_string(n_bytes)
    mock_new_invoice.return_value = (True,
                                     new_invoice(1, InvoiceStatus.pending,
                                                 bid))
    post_rv = client.post('/order',
                          data={
                              'bid': bid,
                              'message': msg.encode(),
                              'regions': 'a'
                          })
    assert post_rv.status_code == HTTPStatus.BAD_REQUEST
    post_rv = client.post('/order',
                          data={
                              'bid': bid,
                              'message': msg.encode(),
                              'regions': 1
                          })
    assert post_rv.status_code == HTTPStatus.BAD_REQUEST
    post_rv = client.post('/order',
                          data={
                              'bid': bid,
                              'message': msg.encode(),
                              'regions': [[6, 1]]
                          })
    assert post_rv.status_code == HTTPStatus.BAD_REQUEST


@patch('orders.new_invoice')
def test_sent_or_received_criteria_met_successfully_for_subset_of_regions(
        mock_new_invoice, client):
    selected_regions = [
        Regions.g18.value, Regions.e113.value, Regions.t11n_afr.value
    ]
    uuid = generate_test_order(mock_new_invoice,
                               client,
                               tx_seq_num=1,
                               order_status=OrderStatus.transmitting,
                               regions=selected_regions)['uuid']
    db_order = Order.query.filter_by(uuid=uuid).first()

    # Only the selected regions are required to confirm Tx in order for the
    # order to change into "sent" state.
    post_rv = client.post('/order/tx/1', data={'regions': [selected_regions]})
    assert post_rv.status_code == HTTPStatus.OK
    db_tx_confirmation = TxConfirmation.query.filter_by(
        order_id=db_order.id).order_by(TxConfirmation.region_id).all()
    assert len(db_tx_confirmation) == 3
    assert db_tx_confirmation[0].region_id == SATELLITE_REGIONS[
        Regions.g18]['id']
    assert db_tx_confirmation[1].region_id == SATELLITE_REGIONS[
        Regions.e113]['id']
    assert db_tx_confirmation[2].region_id == SATELLITE_REGIONS[
        Regions.t11n_afr]['id']
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.sent.value

    # Confirm rx only for the monitored regions in the order request (i.e.,
    # excluding t11n_afr)
    for region in [Regions.g18.value, Regions.e113.value]:
        post_rv = client.post('/order/rx/1', data={'region': region})
        assert post_rv.status_code == HTTPStatus.OK

    # The order's status should change to received
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.received.value

    # A synthesized Rx confirmation should be created for t11n_afr
    db_rx_confirmation = RxConfirmation.query.filter_by(
        order_id=db_order.id).filter_by(presumed=True).all()
    assert len(db_rx_confirmation) == 1
    assert db_rx_confirmation[0].region_id == SATELLITE_REGIONS[
        Regions.t11n_afr]['id']


@patch('orders.new_invoice')
def test_sent_or_received_criteria_met_for_subset_of_presumed_rx_regions(
        mock_new_invoice, client):
    selected_regions = [Regions.t11n_afr.value, Regions.t11n_eu.value]
    uuid = generate_test_order(mock_new_invoice,
                               client,
                               tx_seq_num=1,
                               order_status=OrderStatus.transmitting,
                               regions=selected_regions)['uuid']
    db_order = Order.query.filter_by(uuid=uuid).first()

    # Confirm tx only for the two selected regions
    post_rv = client.post('/order/tx/1', data={'regions': [selected_regions]})
    assert post_rv.status_code == HTTPStatus.OK

    # The order status should change to received and NOT sent. The two regions
    # in the order request were t11n_afr and t11n_eu. None of these regions
    # send Rx confirmations. As a result, the order should automatically move
    # from sent to received without any Rx confirmations.
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.received.value

    # The synthesized Rx confirmations for Africa and Europe should be created
    db_rx_confirmation = RxConfirmation.query.filter_by(
        order_id=db_order.id).filter_by(presumed=True).all()
    assert len(db_rx_confirmation) == 2
    assert db_rx_confirmation[0].region_id == SATELLITE_REGIONS[
        Regions.t11n_afr]['id']
    assert db_rx_confirmation[1].region_id == SATELLITE_REGIONS[
        Regions.t11n_eu]['id']


@patch('orders.new_invoice')
def test_sent_or_received_criteria_met_invalid_tx_subset(
        mock_new_invoice, client):
    selected_regions = [Regions.g18.value, Regions.e113.value]
    other_regions = [
        Regions.t11n_afr.value, Regions.t11n_eu.value, Regions.t18v_c.value,
        Regions.t18v_ku.value
    ]
    uuid = generate_test_order(mock_new_invoice,
                               client,
                               tx_seq_num=1,
                               order_status=OrderStatus.transmitting,
                               regions=selected_regions)['uuid']
    db_order = Order.query.filter_by(uuid=uuid).first()

    # Confirm tx over regions other than those explicitly requested
    # by the order
    post_rv = client.post('/order/tx/1', data={'regions': [other_regions]})
    assert post_rv.status_code == HTTPStatus.OK

    # The order status should change to "confirming"
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.confirming.value

    # Confirm tx
    post_rv = client.post('/order/tx/1', data={'regions': [selected_regions]})
    assert post_rv.status_code == HTTPStatus.OK
    # Now the status should get updated to sent
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.sent.value

    # Confirm rx
    for region in other_regions:
        post_rv = client.post('/order/rx/1', data={'region': region})
        assert post_rv.status_code == HTTPStatus.OK
    # The status should stay as sent so long as rx is not confirmed
    # by the two regions in the request (g18, e113)
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.sent.value

    for region in [Regions.g18.value, Regions.e113.value]:
        post_rv = client.post('/order/rx/1', data={'region': region})
        assert post_rv.status_code == HTTPStatus.OK
    # Now the status should change to received
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.received.value
