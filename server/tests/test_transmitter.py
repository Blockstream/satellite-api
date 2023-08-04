import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from common import generate_test_order, pay_invoice, confirm_tx
from constants import InvoiceStatus, OrderStatus, USER_CHANNEL
import transmitter
from database import db
from schemas import order_schema
from models import Order, TxRetry, TxConfirmation
from regions import Regions, all_region_numbers, region_number_list_to_code
from order_helpers import refresh_retransmission_table, \
    get_next_retransmission, sent_or_received_criteria_met, assert_order_state
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
    msg = json.dumps(msg)
    mockredis.publish.assert_called_with(channel='transmissions', message=msg)


@patch('orders.new_invoice')
def test_tx_start(mock_new_invoice, client, mockredis):
    # Create two orders and pay only for the first.
    first_order_uuid = generate_test_order(mock_new_invoice, client)['uuid']
    second_order_uuid = generate_test_order(mock_new_invoice,
                                            client,
                                            order_id=2)['uuid']

    first_db_order = Order.query.filter_by(uuid=first_order_uuid).first()

    # The transmission should start immediately upon payment
    pay_invoice(first_db_order.invoices[0], client)
    assert_redis_call(mockredis, first_db_order)

    # The expectation is that the first order gets transmitted and the second
    # stays untouched. The invoice callback handler should call tx_start.
    assert_order_state(first_order_uuid, 'transmitting')
    assert first_db_order.tx_seq_num is not None
    assert_order_state(second_order_uuid, 'pending')
    second_db_order = Order.query.filter_by(uuid=second_order_uuid).first()
    assert second_db_order.tx_seq_num is None

    # Calling tx_start explicitly won't change anything since the second order
    # is still unpaid
    transmitter.tx_start()
    second_db_order = Order.query.filter_by(uuid=second_order_uuid).first()
    assert second_db_order.status == OrderStatus.pending.value
    assert second_db_order.tx_seq_num is None


@patch('orders.new_invoice')
def test_tx_end(mock_new_invoice, client, mockredis):
    # Create two orders and pay for both.
    first_order_uuid = generate_test_order(mock_new_invoice, client,
                                           bid=2000)['uuid']
    second_order_uuid = generate_test_order(mock_new_invoice,
                                            client,
                                            bid=1000,
                                            order_id=2)['uuid']

    first_db_order = Order.query.filter_by(uuid=first_order_uuid).first()
    second_db_order = Order.query.filter_by(uuid=second_order_uuid).first()

    # As soon as the first order is paid, its transmission should start
    # immediately.
    pay_invoice(first_db_order.invoices[0], client)
    assert_redis_call(mockredis, first_db_order)

    # Meanwhile, if the second order is paid, its transmission cannot start
    # immediately because the Tx line is still blocked by the first order.
    pay_invoice(second_db_order.invoices[0], client)

    # The expectation is that the first order gets transmitted and the second
    # stays in paid state. The invoice callback handler should call tx_start.
    assert_order_state(first_order_uuid, 'transmitting')
    assert first_db_order.tx_seq_num is not None
    assert_order_state(second_order_uuid, 'paid')
    assert second_db_order.tx_seq_num is None

    # The second order should start transmitting immediately after ending the
    # first. The only prerequisite is that the first order is in sent state
    # (after Tx confirmations) when ended.
    confirm_tx(first_db_order.tx_seq_num, all_region_numbers, client)
    if sent_or_received_criteria_met(first_db_order):
        transmitter.tx_end(first_db_order)

    assert_order_state(first_order_uuid, 'sent')
    assert first_db_order.ended_transmission_at is not None
    assert_order_state(second_order_uuid, 'transmitting')
    assert second_db_order.tx_seq_num is not None


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
def test_startup_sequence(mock_new_invoice, client, mockredis):
    # create an old transmitted order
    transmitting_order_uuid = generate_test_order(
        mock_new_invoice,
        client,
        invoice_status=InvoiceStatus.paid,
        order_status=OrderStatus.transmitting,
        started_transmission_at=datetime.utcnow() -
        timedelta(minutes=5))['uuid']

    # create two paid orders
    first_sendable_order_uuid = generate_test_order(mock_new_invoice,
                                                    client,
                                                    order_id=5,
                                                    bid=1000)['uuid']
    second_sendable_order_uuid = generate_test_order(mock_new_invoice,
                                                     client,
                                                     order_id=6,
                                                     bid=2000)['uuid']
    first_sendable_db_order = \
        Order.query.filter_by(uuid=first_sendable_order_uuid).first()
    second_sendable_db_order = \
        Order.query.filter_by(uuid=second_sendable_order_uuid).first()

    pay_invoice(first_sendable_db_order.invoices[0], client)
    pay_invoice(second_sendable_db_order.invoices[0], client)

    # At startup, tx_start() should trigger the transmission of the highest
    # bidder among the two paid orders, namely the second sendable order.
    # However, this transmission is not possible until the transmitting order
    # from the previous session times out and changes to confirming state.
    transmitter.tx_start()
    assert_order_state(first_sendable_order_uuid, 'paid')
    assert_order_state(second_sendable_order_uuid, 'paid')

    # Force the timeout by manipulating the transmission timestamp.
    transmitting_db_order = \
        Order.query.filter_by(uuid=transmitting_order_uuid).first()
    transmitting_db_order.started_transmission_at = datetime.utcnow(
    ) - timedelta(seconds=constants.DEFAULT_TX_CONFIRM_TIMEOUT_SECS + 1)
    db.session.commit()
    refresh_retransmission_table()
    assert_order_state(transmitting_order_uuid, 'confirming')

    # Now, tx_start() can trigger the new transmission.
    transmitter.tx_start()
    assert_order_state(first_sendable_order_uuid, 'paid')
    assert_order_state(second_sendable_order_uuid, 'transmitting')

    # At this point, the Tx hosts send Tx confirmations
    confirm_tx(second_sendable_db_order.tx_seq_num, all_region_numbers, client)

    # Finally, tx_end() shall end the first transmission and trigger the second
    # transmission (the first sendable order).
    transmitter.tx_end(second_sendable_db_order)
    assert_order_state(first_sendable_order_uuid, 'transmitting')
    assert_order_state(second_sendable_order_uuid, 'sent')

    # The sequence numbers should reflect the transmission order
    assert first_sendable_db_order.tx_seq_num == 2
    assert second_sendable_db_order.tx_seq_num == 1


@patch('orders.new_invoice')
def test_retransmission(mock_new_invoice, client, mockredis):
    # 1) Order that requires retransmission due to not being confirmed
    #    by all Tx regions within the time limit.
    first_order_gen_resp = generate_test_order(mock_new_invoice,
                                               client,
                                               bid=1000)
    first_order_uuid = first_order_gen_resp['uuid']
    first_order_auth_token = first_order_gen_resp['auth_token']

    # Pay invoice -> State changes from pending to transmitting.
    first_order = Order.query.filter_by(uuid=first_order_uuid).first()
    pay_invoice(first_order.invoices[0], client)
    assert_order_state(first_order_uuid, 'transmitting')
    assert_redis_call(mockredis, first_order)

    # Confirm Tx over a single region -> State changes from transmitting to
    # confirming.
    confirm_tx(1, [all_region_numbers[0]], client)
    assert_order_state(first_order_uuid, 'confirming')

    # Manipulate the Tx confirmation timestamp such that it exceeds the time
    # limit and later leads to a retransmission.
    last_tx_confirmation = TxConfirmation.query.filter_by(
        order_id=first_order.id).order_by(
            TxConfirmation.created_at.desc()).first()
    last_tx_confirmation.created_at = datetime.utcnow() - timedelta(
        seconds=constants.DEFAULT_TX_CONFIRM_TIMEOUT_SECS + 1)
    db.session.commit()

    # 2) Order that needs retransmission due to not receiving any confirmation
    #    at all within the timeout limit.
    second_order_gen_resp = generate_test_order(mock_new_invoice,
                                                client,
                                                bid=2000)
    second_order_uuid = second_order_gen_resp['uuid']
    second_order_auth_token = second_order_gen_resp['auth_token']

    # Pay invoice -> State changes from pending to transmitting.
    second_order = Order.query.filter_by(uuid=second_order_uuid).first()
    pay_invoice(second_order.invoices[0], client)
    assert_order_state(second_order_uuid, 'transmitting')
    assert_redis_call(mockredis, second_order)

    # Manipulate the Tx start timestamp such that it exceeds the time limit and
    # later leads to a retransmission.
    second_order.started_transmission_at = datetime.utcnow() - timedelta(
        seconds=constants.DEFAULT_TX_CONFIRM_TIMEOUT_SECS + 1)
    db.session.commit()

    # 3) Order that transmits normally with no need for retransmission.
    third_order_regions = [Regions.g18.value, Regions.e113.value]
    third_order_gen_resp = generate_test_order(mock_new_invoice,
                                               client,
                                               bid=2000,
                                               regions=third_order_regions)
    third_order_uuid = third_order_gen_resp['uuid']
    third_order_auth_token = third_order_gen_resp['auth_token']

    # Pay invoice. In this case, the state changes from pending to paid (not to
    # transmitting) since the Tx line is still blocked by the second order.
    third_order = Order.query.filter_by(uuid=third_order_uuid).first()
    pay_invoice(third_order.invoices[0], client)
    assert_order_state(third_order_uuid, 'paid')

    # So far, none of the orders should have retransmission info
    assert first_order.retransmission is None
    assert second_order.retransmission is None
    assert third_order.retransmission is None

    # Detect and update all the required retransmissions
    refresh_retransmission_table()

    # The first and second orders should require retransmission. Also, the
    # second order should have changed from transmitting to confirming.
    retry_orders = TxRetry.query.all()
    assert len(retry_orders) == 2
    assert retry_orders[0].order_id == first_order.id
    assert retry_orders[1].order_id == second_order.id
    assert first_order.retransmission is not None
    assert second_order.retransmission is not None
    assert third_order.retransmission is None
    assert_order_state(second_order_uuid, 'confirming')

    # Check the next order for retransmission, which should be the highest
    # bidder among the two with pending retransmission (the second order)
    order, retry_info = get_next_retransmission(USER_CHANNEL)
    assert order and retry_info
    assert order.id == second_order.id
    assert retry_info.order_id == second_order.id

    # At this point, a worker would see orders requiring retransmission and
    # call tx_start.
    transmitter.tx_start()

    # The third order should be prioritized because it's not a retransmission.
    assert_order_state(third_order_uuid, 'transmitting')
    assert_redis_call(mockredis, third_order)

    # So, at this point, the retransmissions do not have a timestamp yet.
    assert first_order.retransmission.last_attempt is None
    assert second_order.retransmission.last_attempt is None
    assert third_order.retransmission is None

    # Confirm Tx for all regions. That should end the transmission and kick off
    # the next, namely the retransmission of the second order. When the
    # retransmission starts, the second order goes back from confirming to
    # transmitting state.
    confirm_tx(3, third_order_regions, client)
    assert_order_state(third_order_uuid, 'sent')
    assert_order_state(second_order_uuid, 'transmitting')
    assert_redis_call(mockredis, second_order)

    # The retransmission that was triggered should have a timestamp
    assert first_order.retransmission.last_attempt is None
    assert second_order.retransmission.last_attempt is not None
    assert third_order.retransmission is None

    # Now, pretend the second order received all the required confirmations
    # such that its transmission ended and the next started.
    confirm_tx(second_order.tx_seq_num, all_region_numbers, client)
    assert_order_state(second_order_uuid, 'sent')

    # tx_end (called under the hood by the Tx confirmation handler) should
    # remove the second order from the tx_retries table and start transmitting
    # the next order, namely the retransmission of the first.
    retry_orders = TxRetry.query.all()
    assert len(retry_orders) == 1
    assert retry_orders[0].order_id == first_order.id
    assert retry_orders[0].retry_count == 1
    assert retry_orders[0].last_attempt is not None
    assert first_order.retransmission.last_attempt is not None
    assert second_order.retransmission is None  # info removed
    assert third_order.retransmission is None
    assert_order_state(first_order_uuid, 'transmitting')

    # Besides, since the first order was confirmed by the first region before,
    # now the retransmission should go over the remaining regions only.
    expected_redis_order = first_order
    expected_redis_order.region_code = region_number_list_to_code(
        all_region_numbers[1:])
    assert_redis_call(mockredis, expected_redis_order)

    # Next, suppose no confirmations are sent for the first retransmission.
    # That should lead to a second retransmission. Manipulate the
    # retransmission info to make that happen.
    t_last_attempt = first_order.retransmission.last_attempt
    first_order.retransmission.last_attempt = t_last_attempt - \
        timedelta(seconds=constants.DEFAULT_TX_CONFIRM_TIMEOUT_SECS + 1)
    db.session.commit()

    # A worker would timeout the order and put it back to confirming state.
    refresh_retransmission_table()
    assert_order_state(first_order_uuid, 'confirming')

    # Another worker would see the confirming order and call tx_start(),
    # leading to the second retransmission.
    transmitter.tx_start()
    assert_order_state(first_order_uuid, 'transmitting')
    assert_redis_call(mockredis, expected_redis_order)
    retry_order = TxRetry.query.all()
    assert len(retry_order) == 1
    assert retry_order[0].order_id == first_order.id
    assert retry_order[0].retry_count == 2
    assert first_order.retransmission.retry_count == 2
    assert second_order.retransmission is None
    assert third_order.retransmission is None

    # Lastly, suppose this second retransmission receives Tx confirmations, but
    # not all of the required ones. Hence, it should be retransmitted one more
    # time. Again, manipulate the retransmission info to make that happen. This
    # time, note it's the wait interval that determines the retransmission, not
    # the timeout interval. Also, the wait interval should be applied to the
    # last (most recent) Tx confirmation, not the last retransmission time.
    confirm_tx(first_order.tx_seq_num, all_region_numbers[1:3], client)
    assert_order_state(first_order_uuid, 'confirming')

    for order in first_order.tx_confirmations:
        order.created_at = datetime.utcnow() - timedelta(
            seconds=constants.DEFAULT_TX_CONFIRM_TIMEOUT_SECS + 1)
    db.session.commit()

    transmitter.tx_start()
    assert_order_state(first_order_uuid, 'transmitting')
    retry_order = TxRetry.query.all()
    assert len(retry_order) == 1
    assert retry_order[0].order_id == first_order.id
    assert retry_order[0].retry_count == 3
    assert first_order.retransmission.retry_count == 3
    assert second_order.retransmission is None
    assert third_order.retransmission is None

    # A repeated Tx confirmation should not put the order back into confirming
    # state. Otherwise, another retransmission would be triggered.
    confirm_tx(first_order.tx_seq_num, all_region_numbers[1:3], client)
    assert_order_state(first_order_uuid, 'transmitting')
    assert first_order.retransmission.retry_count == 3

    # The retransmission information should be returned by the
    # /admin/order/:uuid endpoint or the /admin/orders/:state endpoint
    get_rv1_admin = client.get(
        f'/admin/order/{first_order_uuid}',
        headers={'X-Auth-Token': first_order_auth_token})
    get_rv2_admin = client.get(
        f'/admin/order/{second_order_uuid}',
        headers={'X-Auth-Token': second_order_auth_token})
    get_rv3_admin = client.get(
        f'/admin/order/{third_order_uuid}',
        headers={'X-Auth-Token': third_order_auth_token})
    get_rv4_admin = client.get('/admin/orders/retransmitting')
    assert get_rv1_admin.get_json()['retransmission']['last_attempt'] == \
        first_order.retransmission.last_attempt.isoformat()
    assert get_rv2_admin.get_json()['retransmission'] is None
    assert get_rv3_admin.get_json()['retransmission'] is None
    assert len(get_rv4_admin.get_json()) == 1
    assert get_rv4_admin.get_json()[0]['uuid'] == first_order_uuid
    assert get_rv4_admin.get_json()[0]['retransmission']['retry_count'] == 3

    # But it should be omitted in the corresponding non-admin endpoints
    get_rv1_non_admin = client.get(
        f'/order/{first_order_uuid}',
        headers={'X-Auth-Token': first_order_auth_token})
    get_rv4_non_admin = client.get('/orders/retransmitting')
    assert len(get_rv4_non_admin.get_json()) == 1
    assert 'retransmission' not in get_rv1_non_admin.get_json()
    assert 'retransmission' not in get_rv4_non_admin.get_json()[0]


@patch('orders.new_invoice')
def test_multichannel_transmission(mock_new_invoice, client, mockredis):
    # Post orders on the gossip and btc-src channels via the admin endpoint
    gossip_order_uuid1 = generate_test_order(mock_new_invoice,
                                             client,
                                             order_id=1,
                                             bid=1000,
                                             channel=constants.GOSSIP_CHANNEL,
                                             admin=True)['uuid']
    gossip_order_uuid2 = generate_test_order(mock_new_invoice,
                                             client,
                                             order_id=2,
                                             bid=1000,
                                             channel=constants.GOSSIP_CHANNEL,
                                             admin=True)['uuid']
    btc_order_uuid1 = generate_test_order(mock_new_invoice,
                                          client,
                                          order_id=3,
                                          bid=2000,
                                          channel=constants.BTC_SRC_CHANNEL,
                                          admin=True)['uuid']

    btc_order_uuid2 = generate_test_order(mock_new_invoice,
                                          client,
                                          order_id=4,
                                          bid=2000,
                                          channel=constants.BTC_SRC_CHANNEL,
                                          admin=True)['uuid']

    # Post regular user-channel orders (requiring payment)
    user_order_uuid1 = generate_test_order(mock_new_invoice,
                                           client,
                                           order_id=5,
                                           bid=1000)['uuid']
    user_order_uuid2 = generate_test_order(mock_new_invoice,
                                           client,
                                           order_id=6,
                                           bid=2000)['uuid']

    gossip_db_order1 = \
        Order.query.filter_by(uuid=gossip_order_uuid1).first()
    btc_db_order1 = \
        Order.query.filter_by(uuid=btc_order_uuid1).first()
    user_db_order1 = \
        Order.query.filter_by(uuid=user_order_uuid1).first()

    # The first admin orders should immediately move to the transmitting state.
    # The second admin orders are in paid state (auto/forcedly paid) and
    # waiting. The user orders are both in pending state until payment.
    assert_order_state(gossip_order_uuid1, 'transmitting')
    assert_order_state(gossip_order_uuid2, 'paid')
    assert_order_state(btc_order_uuid1, 'transmitting')
    assert_order_state(btc_order_uuid2, 'paid')
    assert_order_state(user_order_uuid1, 'pending')
    assert_order_state(user_order_uuid2, 'pending')

    # Pay for the first user-channel order and ensure it moves to the
    # transmitting state while the ongoing transmissions in other channels
    # remain in progress simultaneously
    pay_invoice(user_db_order1.invoices[0], client)
    assert_order_state(user_order_uuid1, 'transmitting')
    assert_order_state(gossip_order_uuid1, 'transmitting')
    assert_order_state(btc_order_uuid1, 'transmitting')

    # Calling tx_start should have no impact on the state
    transmitter.tx_start()
    transmitter.tx_start(constants.GOSSIP_CHANNEL)
    transmitter.tx_start(constants.BTC_SRC_CHANNEL)
    assert_order_state(gossip_order_uuid1, 'transmitting')
    assert_order_state(gossip_order_uuid2, 'paid')
    assert_order_state(btc_order_uuid1, 'transmitting')
    assert_order_state(btc_order_uuid2, 'paid')
    assert_order_state(user_order_uuid1, 'transmitting')
    assert_order_state(user_order_uuid2, 'pending')

    # Next, assume the Tx hosts send Tx confirmations
    confirm_tx(gossip_db_order1.tx_seq_num, all_region_numbers, client)
    confirm_tx(btc_db_order1.tx_seq_num, all_region_numbers, client)
    confirm_tx(user_db_order1.tx_seq_num, all_region_numbers, client)

    # Once confirmed, the next admin orders should start automatically. The
    # next user order does not start because the payment is still missing.
    assert_order_state(gossip_order_uuid1, 'sent')
    assert_order_state(gossip_order_uuid2, 'transmitting')
    assert_order_state(btc_order_uuid1, 'sent')
    assert_order_state(btc_order_uuid2, 'transmitting')
    assert_order_state(user_order_uuid1, 'sent')
    assert_order_state(user_order_uuid2, 'pending')


def generate_paid_test_orders():
    user_channel_order_1 = Order(uuid='uuid_user',
                                 unpaid_bid=2000,
                                 message_size=10,
                                 message_digest='some digest',
                                 status=OrderStatus.paid.value)
    gossip_order = Order(uuid='uuid_gossip',
                         unpaid_bid=2000,
                         message_size=10,
                         message_digest='some digest',
                         status=OrderStatus.paid.value,
                         channel=constants.GOSSIP_CHANNEL)
    btc_order = Order(uuid='uuid_btc',
                      unpaid_bid=2000,
                      message_size=10,
                      message_digest='some digest',
                      status=OrderStatus.paid.value,
                      channel=constants.BTC_SRC_CHANNEL)
    auth_order = Order(uuid='uuid_auth',
                       unpaid_bid=2000,
                       message_size=10,
                       message_digest='some digest',
                       status=OrderStatus.paid.value,
                       channel=constants.AUTH_CHANNEL)
    db.session.add(user_channel_order_1)
    db.session.add(gossip_order)
    db.session.add(btc_order)
    db.session.add(auth_order)
    db.session.commit()


def test_tx_start_with_single_channel(client):
    generate_paid_test_orders()
    transmitter.tx_start(constants.USER_CHANNEL)
    assert_order_state('uuid_user', 'transmitting')
    assert_order_state('uuid_gossip', 'paid')
    assert_order_state('uuid_btc', 'paid')
    assert_order_state('uuid_auth', 'paid')

    transmitter.tx_start(constants.GOSSIP_CHANNEL)
    assert_order_state('uuid_user', 'transmitting')
    assert_order_state('uuid_gossip', 'transmitting')
    assert_order_state('uuid_btc', 'paid')
    assert_order_state('uuid_auth', 'paid')

    transmitter.tx_start(constants.BTC_SRC_CHANNEL)
    assert_order_state('uuid_user', 'transmitting')
    assert_order_state('uuid_gossip', 'transmitting')
    assert_order_state('uuid_btc', 'transmitting')
    assert_order_state('uuid_auth', 'paid')

    transmitter.tx_start(constants.AUTH_CHANNEL)
    assert_order_state('uuid_user', 'transmitting')
    assert_order_state('uuid_gossip', 'transmitting')
    assert_order_state('uuid_btc', 'transmitting')
    assert_order_state('uuid_auth', 'transmitting')


def test_tx_start_without_channel(client):
    generate_paid_test_orders()
    transmitter.tx_start()
    assert_order_state('uuid_user', 'transmitting')
    assert_order_state('uuid_gossip', 'transmitting')
    assert_order_state('uuid_btc', 'transmitting')
    assert_order_state('uuid_auth', 'transmitting')
