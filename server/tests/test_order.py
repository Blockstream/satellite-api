import io
import os
import pytest
from http import HTTPStatus
from unittest.mock import patch
from uuid import uuid4

from constants import InvoiceStatus, OrderStatus, Regions
from database import db
from error import assert_error, get_http_error_resp
from models import Invoice, Order, RxConfirmation, TxConfirmation
from invoice_helpers import pay_invoice
from order_helpers import adjust_bids, _paid_invoices_total,\
    _unpaid_invoices_total
from utils import hmac_sha256_digest
import bidding
import constants
import server

from common import check_invoice, check_upload, new_invoice,\
    place_order, generate_test_order, rnd_string, upload_test_file


@pytest.fixture
def client():
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
    n_bytes = constants.MAX_MESSAGE_SIZE + 1
    rv = place_order(client, n_bytes)
    assert_error(rv.get_json(), 'MESSAGE_FILE_TOO_LARGE')
    assert rv.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE


@patch('orders.new_invoice')
def test_uploaded_file_max_size(mock_new_invoice, client):
    n_bytes = constants.MAX_MESSAGE_SIZE
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

    get_rv = client.get(f'/order/{uuid}',
                        headers={'X-Auth-Token': json_response['auth_token']})
    get_json_resp = get_rv.get_json()
    assert get_rv.status_code == HTTPStatus.OK
    assert get_json_resp['uuid'] == uuid


@patch('orders.new_invoice')
def test_get_order_auth_token_as_form_param(mock_new_invoice, client):
    json_response = generate_test_order(mock_new_invoice, client)
    uuid = json_response['uuid']

    get_rv = client.get(f'/order/{uuid}',
                        data={'auth_token': json_response['auth_token']})
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
    pay_invoice(db_order.invoices[0])
    db_order.tx_seq_num = 1
    db.session.commit()

    # Try to get sent_message for a paid order by sequence number. sent_message
    # can only be retrieved for transmitting, sent, or received messages.
    rv = client.get('/message/1')
    assert rv.status_code == HTTPStatus.NOT_FOUND
    assert_error(rv.get_json(), 'SEQUENCE_NUMBER_NOT_FOUND')


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
    assert post_rv.status_code == HTTPStatus.NOT_FOUND
    assert_error(post_rv.get_json(), 'REGION_NOT_FOUND')


@patch('orders.new_invoice')
def test_confirm_tx(mock_new_invoice, client):
    uuid = generate_test_order(mock_new_invoice, client, tx_seq_num=1)['uuid']
    db_order = Order.query.filter_by(uuid=uuid).first()

    # Confirm tx for a single region
    post_rv = client.post(
        '/order/tx/1', data={'regions': [[constants.Regions.t11n_afr.value]]})
    assert post_rv.status_code == HTTPStatus.OK
    db_tx_confirmation = TxConfirmation.query.filter_by(
        order_id=db_order.id).all()
    assert len(db_tx_confirmation) == 1
    assert db_tx_confirmation[0].region_id == constants.SATELLITE_REGIONS[
        constants.Regions.t11n_afr]['id']

    # Confirm tx for multiple regions
    post_rv = client.post('/order/tx/1',
                          data={
                              'regions': [[
                                  constants.Regions.g18.value,
                                  constants.Regions.e113.value,
                                  constants.Regions.t11n_afr.value
                              ]]
                          })
    assert post_rv.status_code == HTTPStatus.OK
    db_tx_confirmation = TxConfirmation.query.filter_by(
        order_id=db_order.id).order_by(TxConfirmation.region_id).all()
    assert len(db_tx_confirmation) == 3
    assert db_tx_confirmation[0].region_id == constants.SATELLITE_REGIONS[
        constants.Regions.g18]['id']
    assert db_tx_confirmation[1].region_id == constants.SATELLITE_REGIONS[
        constants.Regions.e113]['id']
    assert db_tx_confirmation[2].region_id == constants.SATELLITE_REGIONS[
        constants.Regions.t11n_afr]['id']


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
    assert post_rv.status_code == HTTPStatus.NOT_FOUND
    assert_error(post_rv.get_json(), 'REGION_NOT_FOUND')


@patch('orders.new_invoice')
def test_confirm_rx(mock_new_invoice, client):
    uuid = generate_test_order(mock_new_invoice, client, tx_seq_num=1)['uuid']
    db_order = Order.query.filter_by(uuid=uuid).first()

    post_rv = client.post('/order/rx/1',
                          data={'region': constants.Regions.g18.value})
    assert post_rv.status_code == HTTPStatus.OK
    db_rx_confirmation = RxConfirmation.query.filter_by(
        order_id=db_order.id).all()
    assert len(db_rx_confirmation) == 1
    assert db_rx_confirmation[0].region_id == constants.SATELLITE_REGIONS[
        constants.Regions.g18]['id']


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
def test_received_criteria_met_inadequate_regions(mock_new_invoice, client,
                                                  tx_regions, rx_regions):
    uuid = generate_test_order(mock_new_invoice,
                               client,
                               order_status=OrderStatus.sent,
                               tx_seq_num=1)['uuid']

    # Confirm tx
    post_rv = client.post('/order/tx/1', data={'regions': [tx_regions]})
    assert post_rv.status_code == HTTPStatus.OK

    # Confirm rx
    for region in rx_regions:
        post_rv = client.post('/order/rx/1', data={'region': region})
        assert post_rv.status_code == HTTPStatus.OK

    # Order status should not change to sent because not enough regions have
    # confirmed tx/rx
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.sent.value


@patch('orders.new_invoice')
def test_received_criteria_met_for_unsent_order(mock_new_invoice, client):
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
    assert db_order.status != OrderStatus.received.value
    assert db_order.status == OrderStatus.pending.value


@patch('orders.new_invoice')
def test_received_criteria_met_successfully(mock_new_invoice, client):
    uuid = generate_test_order(mock_new_invoice,
                               client,
                               order_status=OrderStatus.sent,
                               tx_seq_num=1)['uuid']

    # Confirm tx for all 6 regions
    post_rv = client.post('/order/tx/1',
                          data={'regions': [[e.value for e in Regions]]})
    assert post_rv.status_code == HTTPStatus.OK
    # Order's status should still be sent
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
                region_id=constants.SATELLITE_REGIONS[region]['id']).all()
        assert len(db_rx_confirmation) == 1
        assert db_rx_confirmation[0].presumed


@patch('orders.new_invoice')
def test_confirm_tx_repeated_regions(mock_new_invoice, client):
    uuid = generate_test_order(mock_new_invoice, client, tx_seq_num=1)['uuid']
    db_order1 = Order.query.filter_by(uuid=uuid).first()

    uuid = generate_test_order(mock_new_invoice, client, tx_seq_num=2)['uuid']
    db_order2 = Order.query.filter_by(uuid=uuid).first()

    # Confirm tx for a single region
    post_rv = client.post(
        '/order/tx/1', data={'regions': [[constants.Regions.t11n_afr.value]]})
    assert post_rv.status_code == HTTPStatus.OK
    db_tx_confirmation = TxConfirmation.query.filter_by(
        order_id=db_order1.id).all()
    assert len(db_tx_confirmation) == 1

    # Re-Confirm tx for the same region
    post_rv = client.post(
        '/order/tx/1', data={'regions': [[constants.Regions.t11n_afr.value]]})
    assert post_rv.status_code == HTTPStatus.OK
    db_tx_confirmation = TxConfirmation.query.filter_by(
        order_id=db_order1.id).all()
    assert len(db_tx_confirmation) == 1

    # Confirm tx for multiple regions, including t11n_afr again
    post_rv = client.post('/order/tx/1',
                          data={
                              'regions': [[
                                  constants.Regions.g18.value,
                                  constants.Regions.t18v_c.value,
                                  constants.Regions.t11n_afr.value
                              ]]
                          })
    assert post_rv.status_code == HTTPStatus.OK
    db_tx_confirmation = TxConfirmation.query.filter_by(
        order_id=db_order1.id).all()
    assert len(db_tx_confirmation) == 3

    # Confirm tx for multiple regions, different order_id
    post_rv = client.post('/order/tx/2',
                          data={
                              'regions': [[
                                  constants.Regions.t11n_eu.value,
                                  constants.Regions.t18v_ku.value,
                                  constants.Regions.t18v_ku.value
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
    post_rv = client.post('/order/rx/1',
                          data={'region': constants.Regions.g18.value})
    assert post_rv.status_code == HTTPStatus.OK
    db_rx_confirmation = RxConfirmation.query.filter_by(
        order_id=db_order1.id).all()
    assert len(db_rx_confirmation) == 1

    # Re-Confirm rx for the same region
    post_rv = client.post('/order/rx/1',
                          data={'region': constants.Regions.g18.value})
    assert post_rv.status_code == HTTPStatus.OK
    db_rx_confirmation = RxConfirmation.query.filter_by(
        order_id=db_order1.id).all()
    assert len(db_rx_confirmation) == 1

    # Confirm rx for the same region, different order_id
    post_rv = client.post('/order/rx/2',
                          data={'region': constants.Regions.g18.value})
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

    # refetch the order and the invoice from the database
    # expecation is that invoice changes its status to paid becasue
    # it had the pending status, but order keeps its current status
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
