import os
import pytest
from datetime import datetime, timedelta
from http import HTTPStatus
from unittest.mock import patch

from constants import EXPIRE_PENDING_ORDERS_AFTER_DAYS, \
    InvoiceStatus, MESSAGE_FILE_RETENTION_TIME_DAYS, \
    OrderStatus, MSG_STORE_PATH
from database import db
from models import Order, TxRetry
from regions import Regions, region_number_list_to_code, region_number_to_id
import order_helpers
import server

from common import generate_test_order


@pytest.fixture
def client():
    app = server.create_app(from_test=True)
    app.app_context().push()
    with app.test_client() as client:
        yield client
    server.teardown_app(app)


@patch('orders.new_invoice')
def test_expire_pending_orders(mock_new_invoice, client):
    to_be_expired_order_uuid = generate_test_order(mock_new_invoice,
                                                   client)['uuid']
    to_be_expired_db_order = Order.query.filter_by(
        uuid=to_be_expired_order_uuid).first()
    to_be_expired_db_order.created_at = datetime.utcnow() - \
        timedelta(days=EXPIRE_PENDING_ORDERS_AFTER_DAYS
                  + 1)
    db.session.commit()

    pending_not_yet_expired_uuid = generate_test_order(mock_new_invoice,
                                                       client,
                                                       order_id=2)['uuid']

    expired_orders = order_helpers.expire_old_pending_orders()
    assert len(expired_orders) == 1
    assert expired_orders[0].uuid == to_be_expired_order_uuid

    # refetch and check
    # expectation is that the order gets expired
    to_be_expired_db_order = Order.query.filter_by(
        uuid=to_be_expired_order_uuid).first()
    assert to_be_expired_db_order.status == OrderStatus.expired.value

    # The pending order whose expiration time has not been reached yet should
    # not get expired
    pending_not_yet_expired_db_order = Order.query.filter_by(
        uuid=pending_not_yet_expired_uuid).first()
    assert pending_not_yet_expired_db_order.status == OrderStatus.pending.value


@patch('orders.new_invoice')
@pytest.mark.parametrize("status", [
    OrderStatus.paid, OrderStatus.transmitting, OrderStatus.sent,
    OrderStatus.received, OrderStatus.cancelled, OrderStatus.expired
])
def test_expire_non_pending_orders(mock_new_invoice, client, status):
    order_uuid = generate_test_order(mock_new_invoice,
                                     client,
                                     order_status=status)['uuid']
    db_order = Order.query.filter_by(uuid=order_uuid).first()
    db_order.created_at = datetime.utcnow() - \
        timedelta(days=EXPIRE_PENDING_ORDERS_AFTER_DAYS
                  + 1)
    db.session.commit()

    order_helpers.expire_old_pending_orders()

    # refetch and check
    # expectation is that the order's status does not change
    db_order = Order.query.filter_by(uuid=order_uuid).first()
    assert db_order.status == status.value


@patch('orders.new_invoice')
def test_cleanup_old_message_files(mock_new_invoice, client):
    to_be_cleaned_order_uuid = generate_test_order(
        mock_new_invoice,
        client,
        order_id=1,
        invoice_status=InvoiceStatus.paid)['uuid']
    to_be_cleaned_db_order = Order.query.filter_by(
        uuid=to_be_cleaned_order_uuid).first()
    to_be_cleaned_db_order.ended_transmission_at = datetime.utcnow() -\
        timedelta(days=MESSAGE_FILE_RETENTION_TIME_DAYS
                  + 1)
    db.session.commit()

    not_to_be_cleaned_order_uuid = generate_test_order(
        mock_new_invoice,
        client,
        order_id=1,
        invoice_status=InvoiceStatus.paid)['uuid']
    not_to_be_cleaned_db_order = Order.query.filter_by(
        uuid=not_to_be_cleaned_order_uuid).first()
    not_to_be_cleaned_db_order.ended_transmission_at = datetime.utcnow() -\
        timedelta(days=MESSAGE_FILE_RETENTION_TIME_DAYS)
    db.session.commit()

    cleaned_up_orders = order_helpers.cleanup_old_message_files()
    assert len(cleaned_up_orders) == 1
    assert cleaned_up_orders[0].uuid == to_be_cleaned_order_uuid

    # refetch and check
    message_path = os.path.join(MSG_STORE_PATH, to_be_cleaned_order_uuid)
    assert not os.path.exists(message_path)
    message_path = os.path.join(MSG_STORE_PATH, not_to_be_cleaned_order_uuid)
    assert os.path.exists(message_path)


@patch('orders.new_invoice')
@pytest.mark.parametrize("status", [
    OrderStatus.paid, OrderStatus.transmitting, OrderStatus.sent,
    OrderStatus.received, OrderStatus.cancelled, OrderStatus.expired
])
def test_maybe_mark_order_as_expired_for_invalid_order(mock_new_invoice,
                                                       client, status):
    # when order does not exist
    assert order_helpers.maybe_mark_order_as_expired(1) is None

    # when order exists, but its status is not pending
    generate_test_order(mock_new_invoice,
                        client,
                        order_id=1,
                        order_status=status)
    assert order_helpers.maybe_mark_order_as_expired(1) is None


@patch('orders.new_invoice')
def test_maybe_mark_order_as_expired_pending_order_has_pending_invoice(
        mock_new_invoice, client):
    # when a pending order has a pending invoice
    generate_test_order(mock_new_invoice, client, order_id=1)
    assert order_helpers.maybe_mark_order_as_expired(1) is None


@patch('orders.new_invoice')
@pytest.mark.parametrize("invoice_status",
                         [InvoiceStatus.paid, InvoiceStatus.expired])
def test_maybe_mark_order_as_expired_successfully(mock_new_invoice, client,
                                                  invoice_status):
    # when a pending order does not have any pending invoice
    uuid = generate_test_order(mock_new_invoice,
                               client,
                               order_id=1,
                               invoice_status=invoice_status)['uuid']
    assert order_helpers.maybe_mark_order_as_expired(1) is not None
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.status == OrderStatus.expired.value


@patch('orders.new_invoice')
def test_upsert_retransmission(mock_new_invoice, client, mockredis):
    uuid = generate_test_order(mock_new_invoice,
                               client,
                               tx_seq_num=1,
                               order_status=OrderStatus.transmitting,
                               regions=[
                                   Regions.g18.value, Regions.e113.value,
                                   Regions.t11n_afr.value,
                                   Regions.t11n_eu.value
                               ])['uuid']

    db_order = Order.query.filter_by(uuid=uuid).first()
    post_rv = client.post(
        '/order/tx/1',
        data={'regions': [[Regions.g18.value, Regions.e113.value]]})
    assert post_rv.status_code == HTTPStatus.OK
    db_order = Order.query.filter_by(uuid=uuid).first()
    order_helpers.upsert_retransmission(db_order)
    # t11n_afr and t11n_eu confirmations are missing
    retry_order = TxRetry.query.filter_by(order_id=db_order.id).first()
    assert retry_order.order_id == db_order.id
    assert retry_order.region_code == region_number_list_to_code(
        [Regions.t11n_afr.value, Regions.t11n_eu.value])

    post_rv = client.post('/order/tx/1',
                          data={'regions': [[Regions.t11n_eu.value]]})
    assert post_rv.status_code == HTTPStatus.OK
    db_order = Order.query.filter_by(uuid=uuid).first()
    order_helpers.upsert_retransmission(db_order)
    # only t11n_afr confirmations are missing
    # expectation is that the existing record in TxRetry gets updated
    retry_order = TxRetry.query.filter_by(order_id=db_order.id).all()
    assert len(retry_order) == 1
    assert retry_order[0].order_id == db_order.id
    assert retry_order[0].region_code == region_number_list_to_code(
        [Regions.t11n_afr.value])


@patch('orders.new_invoice')
def test_upsert_retransmission_for_order_without_regions(
        mock_new_invoice, client):
    uuid = generate_test_order(mock_new_invoice,
                               client,
                               tx_seq_num=1,
                               order_status=OrderStatus.transmitting)['uuid']

    db_order = Order.query.filter_by(uuid=uuid).first()
    post_rv = client.post(
        '/order/tx/1',
        data={'regions': [[Regions.g18.value, Regions.e113.value]]})
    assert post_rv.status_code == HTTPStatus.OK
    db_order = Order.query.filter_by(uuid=uuid).first()
    order_helpers.upsert_retransmission(db_order)
    # No specific region was provided during order creation, so all regions
    # should confrim tx
    retry_order = TxRetry.query.filter_by(order_id=db_order.id).first()
    assert retry_order.order_id == db_order.id
    assert retry_order.region_code == region_number_list_to_code([
        Regions.t11n_afr.value, Regions.t11n_eu.value, Regions.t18v_c.value,
        Regions.t18v_ku.value
    ])


@patch('orders.new_invoice')
def test_upsert_retransmission_for_non_transmitting_order(
        mock_new_invoice, client):
    uuid = generate_test_order(mock_new_invoice,
                               client,
                               order_status=OrderStatus.paid,
                               regions=[
                                   Regions.g18.value, Regions.e113.value,
                                   Regions.t11n_afr.value,
                                   Regions.t11n_eu.value
                               ])['uuid']
    db_order = Order.query.filter_by(uuid=uuid).first()
    order_helpers.upsert_retransmission(db_order)
    # There should be no retransmission record for this order yet since it's
    # not transmitting
    retry_order = TxRetry.query.filter_by(order_id=db_order.id).first()
    assert not retry_order


@patch('orders.new_invoice')
def test_get_missing_tx_confirmations(mock_new_invoice, client):
    selected_regions = [
        Regions.g18.value, Regions.e113.value, Regions.t11n_afr.value,
        Regions.t11n_eu.value
    ]
    uuid = generate_test_order(mock_new_invoice,
                               client,
                               tx_seq_num=1,
                               order_status=OrderStatus.transmitting,
                               regions=selected_regions)['uuid']
    db_order = Order.query.filter_by(uuid=uuid).first()

    # So far, the confirmations from the selected regions should all be missing
    missing_confirmations = order_helpers.get_missing_tx_confirmations(
        db_order)
    assert len(missing_confirmations) == len(selected_regions)
    assert (all([
        region_number_to_id(x) in missing_confirmations
        for x in selected_regions
    ]))

    # Send some Tx confirmations, including one for a region (T18V Ku) that was
    # not part of the original region selection
    post_rv = client.post(
        '/order/tx/1',
        data={
            'regions':
            [[Regions.g18.value, Regions.e113.value, Regions.t18v_ku.value]]
        })
    assert post_rv.status_code == HTTPStatus.OK
    db_order = Order.query.filter_by(uuid=uuid).first()
    missing_confirmations = order_helpers.get_missing_tx_confirmations(
        db_order)
    # Now, only T11N AFR and T11N EU should be missing
    assert (all([
        region_number_to_id(x) in missing_confirmations
        for x in [Regions.t11n_afr.value, Regions.t11n_eu.value]
    ]))


@patch('orders.new_invoice')
def test_get_missing_tx_confirmations_for_non_transmitting_order(
        mock_new_invoice, client):
    uuid = generate_test_order(mock_new_invoice,
                               client,
                               tx_seq_num=1,
                               order_status=OrderStatus.paid,
                               regions=[
                                   Regions.g18.value, Regions.e113.value,
                                   Regions.t11n_afr.value,
                                   Regions.t11n_eu.value
                               ])['uuid']
    db_order = Order.query.filter_by(uuid=uuid).first()
    # There should be no missing Tx confirmation record for this order yet
    # since it's not transmitting
    missing_confirmations = order_helpers.get_missing_tx_confirmations(
        db_order)
    assert len(missing_confirmations) == 0
