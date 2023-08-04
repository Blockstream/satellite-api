import logging
import os
from datetime import datetime, timedelta
from math import ceil

from flask import request
from sqlalchemy import and_, or_, func

from bidding import calc_ota_msg_len, validate_bid
from constants import InvoiceStatus, OrderStatus
from database import db
from error import get_http_error_resp
from models import Order, RxConfirmation, TxConfirmation, TxRetry
from regions import region_number_to_id, monitored_rx_regions, \
    region_code_to_id_list, region_code_to_number_list, \
    region_id_to_number, Regions, region_id_list_to_code
import constants
from utils import hmac_sha256_digest

USER_AUTH_KEY = hmac_sha256_digest('user-token', constants.CHARGE_API_TOKEN)


def compute_auth_token(uuid):
    """Compute the authentication token for a given UUID"""
    return hmac_sha256_digest(USER_AUTH_KEY, uuid)


def _paid_invoices_total(order):
    total = 0
    for invoice in order.invoices:
        if invoice.status == InvoiceStatus.paid.value:
            total += invoice.amount
    return total


def _unpaid_invoices_total(order):
    total = 0
    for invoice in order.invoices:
        if invoice.status == InvoiceStatus.pending.value:
            total += invoice.amount
    return total


def adjust_bids(order):
    order.bid = _paid_invoices_total(order)
    order.bid_per_byte = order.bid / calc_ota_msg_len(order.message_size)
    order.unpaid_bid = _unpaid_invoices_total(order)
    db.session.commit()


def get_and_authenticate_order(uuid, body_args, query_args):
    order = Order.query.filter_by(uuid=uuid).first()

    if order is None:
        return False, get_http_error_resp('ORDER_NOT_FOUND', uuid)

    if 'auth_token' in body_args:
        in_auth_token = body_args.get('auth_token')
    elif 'auth_token' in query_args:
        in_auth_token = query_args.get('auth_token')
    elif 'X-Auth-Token' in request.headers:
        in_auth_token = request.headers.get('X-Auth-Token')
    else:
        return False, get_http_error_resp('INVALID_AUTH_TOKEN')

    expected_auth_token = compute_auth_token(order.uuid)

    if (expected_auth_token != in_auth_token):
        return False, get_http_error_resp('INVALID_AUTH_TOKEN')

    return True, order


def maybe_mark_order_as_paid(order_id):
    order = Order.query.filter_by(id=order_id).first()
    adjust_bids(order)

    if order.status == OrderStatus.pending.value and\
       validate_bid(order.message_size, order.bid):
        order.status = OrderStatus.paid.value
        db.session.commit()


def expire_order(order):
    if order.status == OrderStatus.pending.value:
        logging.info(f"Marking order {order.uuid} as expired")
        order.status = constants.OrderStatus.expired.value
        db.session.commit()
        delete_message_file(order)


def maybe_mark_order_as_expired(order_id):
    """Expire the order if it's pending and has no other pending invoices:"""
    order = Order.query.filter_by(
        id=order_id, status=constants.OrderStatus.pending.value).first()

    if not order:
        return

    n_pending_invoices = 0
    for invoice in order.invoices:
        if invoice.status == InvoiceStatus.pending.value:
            n_pending_invoices += 1

    if n_pending_invoices == 0:
        expire_order(order)
        return order


def delete_message_file(order):
    message_file = os.path.join(constants.MSG_STORE_PATH, order.uuid)
    if os.path.exists(message_file):
        os.remove(message_file)


def synthesize_presumed_rx_confirmations(order):
    presumed = True
    order_region_numbers = region_code_to_number_list(order.region_code)

    # Synthesize rx confirmation:
    # 1- Only for t11n_afr and t11n_eur regions
    # 2- If those regions are part of the requested regions by the order
    for region in [Regions.t11n_afr, Regions.t11n_eu]:
        if region.value in order_region_numbers:
            add_rx_confirmation_if_not_present(order, region, presumed)


def sent_criteria_met(order):
    if order.status in [OrderStatus.sent.value, OrderStatus.received.value]:
        return True

    # If the order is not sent/received, and it's not coming from the
    # transmitting/confirming states, it cannot possibly reach the sent state.
    if order.status not in [
            OrderStatus.transmitting.value, OrderStatus.confirming.value
    ]:
        return False

    # Set of regions on which this order should have been sent
    order_regions = set(region_code_to_id_list(order.region_code))

    # Set of regions with Tx confirmations
    confirmed_tx_regions = set(item.region_id
                               for item in order.tx_confirmations)

    # All regions in order_regions should confirm Tx
    if not (confirmed_tx_regions.issuperset(order_regions)):
        return False

    # Sanity check for unexpected confirmations (useful to detect if the Tx
    # hosts are transmitting orders in the wrong regions)
    if len(confirmed_tx_regions) - len(order_regions) > 0:
        unexpected_region_numbers = \
            [region_id_to_number(x)
             for x in confirmed_tx_regions - order_regions]
        logging.warning(f"Order {order.uuid} has unexpected Tx confirmations: "
                        f"{unexpected_region_numbers}")

    # All the required Tx confirmations were received
    order.status = OrderStatus.sent.value
    db.session.commit()
    return True


def received_criteria_met(order):
    if order.status == OrderStatus.received.value:
        return True

    # If the order is not received yet, and it's not coming from the
    # transmitting/confirming/sent states, it cannot possibly reach the
    # received state in this call.
    if order.status not in [
            OrderStatus.transmitting.value, OrderStatus.confirming.value,
            OrderStatus.sent.value
    ]:
        return False

    # Set of regions on which this order should have been sent
    order_regions = set(region_code_to_id_list(order.region_code))

    # Subset of the order regions that are actually monitored
    expected_rx_confirmations = list(monitored_rx_regions & order_regions)

    # Set of regions with Rx confirmations
    confirmed_rx_regions = set(item.region_id
                               for item in order.rx_confirmations)

    if not (confirmed_rx_regions.issuperset(expected_rx_confirmations)):
        return False

    # Synthesize the remaining Rx confirmations from non-monitored regions.
    synthesize_presumed_rx_confirmations(order)

    # All the required Rx confirmations were received
    order.status = OrderStatus.received.value
    db.session.commit()
    return True


def sent_or_received_criteria_met(order):
    sent = sent_criteria_met(order)
    received = received_criteria_met(order)
    return sent or received


def confirmation_exists(confirmations_table, order_id, region_id):
    confirmations = confirmations_table.query.filter_by(
        order_id=order_id).filter_by(region_id=region_id).all()
    if len(confirmations) > 0:
        return True
    return False


def add_tx_confirmation_if_not_present(order, region_number, presumed=False):
    region_id = region_number_to_id(region_number)
    if not confirmation_exists(TxConfirmation, order.id, region_id):
        # A Tx confirmation indicates that at least one Tx host finished
        # transmitting the order. At this point, the expectation is that the
        # other Tx hosts complete their transmissions soon. In the meantime,
        # change the order state from transmitting to confirming so that other
        # pending orders can be unblocked.
        if order.status == OrderStatus.transmitting.value:
            order.status = OrderStatus.confirming.value
        new_confirmation = TxConfirmation(order_id=order.id,
                                          region_id=region_id,
                                          presumed=presumed)
        db.session.add(new_confirmation)
        db.session.commit()


def add_rx_confirmation_if_not_present(order, region_number, presumed=False):
    region_id = region_number_to_id(region_number)
    if not confirmation_exists(RxConfirmation, order.id, region_id):
        new_confirmation = RxConfirmation(order_id=order.id,
                                          region_id=region_id,
                                          presumed=presumed)
        db.session.add(new_confirmation)
        db.session.commit()


def expire_old_pending_orders():
    """Expire old pending orders

    Expire any pending order that has reached its expiration time.

    Returns:
        List of orders that got expired by this function.

    """
    orders_to_expire = Order.query.filter(
        and_(
            Order.status == constants.OrderStatus.pending.value,
            func.datetime(Order.created_at) < datetime.utcnow() -
            timedelta(days=constants.EXPIRE_PENDING_ORDERS_AFTER_DAYS))).all()
    for order in orders_to_expire:
        expire_order(order)
    return orders_to_expire


def cleanup_old_message_files():
    """Remove message files for old files

    Remove message file for all the orders that have been transmitted more than
    MESSAGE_FILE_RETENTION_TIME_DAYS days ago.

    Returns:
        List of orders whose message file got removed by this function.

    """
    orders_to_cleanup = Order.query.filter(
        func.datetime(Order.ended_transmission_at) < func.datetime(
            datetime.utcnow() -
            timedelta(days=constants.MESSAGE_FILE_RETENTION_TIME_DAYS))).all()
    for order in orders_to_cleanup:
        delete_message_file(order)
    return orders_to_cleanup


def get_missing_tx_confirmations(order):
    """
    Get list of regions that did not confirm tx for this order
    """
    if order.status != constants.OrderStatus.transmitting.value and\
       order.status != constants.OrderStatus.confirming.value:
        return []
    confirmed_tx_regions = set(item.region_id
                               for item in order.tx_confirmations)
    order_regions = set(region_code_to_id_list(order.region_code))
    return list(order_regions - confirmed_tx_regions)


def upsert_retransmission(order):
    """Update or Insert an order in the tx_retries table

    The order gets retransmitted if it meets two criteria:
    1- It has missing tx confirmations.
    2- A certain duration has elapsed since the order was
       transmitted for the first time.

    If the order exists in the orders table but not in the tx_retries table,
    INSERT it. If it exists in both tables, but the list of regions with
    missing confirmations has changed, UPDATE it on the tx_retries table.

    """

    missing_confirmations = get_missing_tx_confirmations(order)
    if len(missing_confirmations) == 0:
        return

    missing_confirmations_code = region_id_list_to_code(missing_confirmations)
    tx_retry_order = TxRetry.query.filter_by(order_id=order.id).first()
    if tx_retry_order:
        tx_retry_order.pending = True
        if tx_retry_order.region_code != missing_confirmations_code:
            tx_retry_order.region_code = missing_confirmations_code
    else:
        new_retry_tx = TxRetry(order_id=order.id,
                               region_code=missing_confirmations_code)
        db.session.add(new_retry_tx)
    db.session.commit()


def refresh_retransmission_table():
    """Update the retransmission table with the orders not confirmed on time

    There are three main conditions to retransmit an order:

    1) The order is in confirming state due to one or more Tx confirmations,
       but its last (most recent) Tx confirmation was received more than
       "tx_confirm_timeout_secs" ago, and not all confirmations were received.
    2) The order is in transmitting state due to a retransmission. It may have
       received Tx confirmations in the past, but not for the retransmission
       (hence why it is in transmitting state). Also, the last retransmission
       was more than "delay + tx_confirm_timeout_secs" seconds ago.
    3) The order has never received any Tx confirmations nor had any
       retransmissions, and it has been like so for more than "delay +
       tx_confirm_timeout_secs" seconds.

    In the last two cases, in which the order is in transmitting state, this
    function immediately changes the order into confirming state so that paid
    orders can be unblocked for transmission.

    Also, the last two cases consider the interval comprising the
    transmission/serialization delay (based on the nominal transmit rate) and
    the Tx confirmation timeout allowance. In contrast, the first case
    considers the timeout interval only, given that its measurement starts
    after the message is already serialized (after the first Tx confirmation).
    Other sources of delay (propagation, routing, etc.) are neglected in both
    cases by assuming "tx_confirm_timeout_secs" is big enough to cover them.

    In summary, the timeout interval (with or without the serialization delay)
    adds to different starting points, as follows:

    1) To the last (most recent) Tx confirmation timestamp.
    2) To the last (most recent) retransmission timestamp.
    3) To the order transmission start timestamp.

    """
    orders = Order.query.filter(
        or_(Order.status == constants.OrderStatus.transmitting.value,
            Order.status == constants.OrderStatus.confirming.value)).all()

    orders_to_retry = []
    for order in orders:
        tx_rate = constants.CHANNEL_INFO[order.channel].tx_rate
        tx_confirm_timeout_secs = constants.CHANNEL_INFO[
            order.channel].tx_confirm_timeout_secs
        tx_delay = int(ceil(calc_ota_msg_len(order.message_size) / tx_rate))
        timeout_interval = tx_delay + tx_confirm_timeout_secs

        last_tx_confirmation = TxConfirmation.query.filter_by(
            order_id=order.id).order_by(
                TxConfirmation.created_at.desc()).first()
        retry_info = TxRetry.query.filter_by(order_id=order.id).first()

        if order.status == constants.OrderStatus.confirming.value and \
                last_tx_confirmation is not None:
            # Case 1
            t_next_retry = last_tx_confirmation.created_at + timedelta(
                seconds=tx_confirm_timeout_secs)
            if datetime.utcnow() > t_next_retry:
                orders_to_retry.append(order)
        elif retry_info and retry_info.retry_count > 0:
            # Case 2
            #
            # The order could have received Tx confirmations previously, but
            # certainly not for the last retransmission, otherwise it would be
            # in confirming state already.
            #
            # NOTE: check case 2 before case 3. If there are no confirmations,
            # but the order has already been retransmitted, the next
            # retransmission time should add to the last retransmission
            # timestamp (here), not the transmission start timestamp (below).
            t_timeout = retry_info.last_attempt + timedelta(
                seconds=timeout_interval)
            if datetime.utcnow() > t_timeout:
                orders_to_retry.append(order)
        elif last_tx_confirmation is None:
            # Case 3
            t_timeout = order.started_transmission_at + timedelta(
                seconds=timeout_interval)
            if datetime.utcnow() > t_timeout:
                orders_to_retry.append(order)

    for order in orders_to_retry:
        if (order.status == OrderStatus.transmitting.value):
            order.status = OrderStatus.confirming.value
            db.session.commit()
        upsert_retransmission(order)


def get_next_retransmission(channel):
    """Get the next highest bidding order requiring retransmission"""
    refresh_retransmission_table()

    orders_with_retry_info = db.session.query(
        Order, TxRetry).filter(Order.id == TxRetry.order_id).filter(
            Order.channel == channel).order_by(
                Order.bid_per_byte.desc()).all()

    for order, retry_info in orders_with_retry_info:
        if retry_info.pending:
            return order, retry_info

    return None, None


def assert_order_state(uuid, state):
    order = Order.query.filter_by(uuid=uuid).first()
    assert order.status == OrderStatus[state].value
