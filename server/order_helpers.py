import datetime
import logging
import os

from flask import request
from sqlalchemy import and_, func

from bidding import calc_ota_msg_len, validate_bid
from constants import InvoiceStatus, OrderStatus
from database import db
from error import get_http_error_resp
from models import Order, RxConfirmation, TxConfirmation
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


def get_and_authenticate_order(uuid, args):
    order = Order.query.filter_by(uuid=uuid).first()

    if order is None:
        return False, get_http_error_resp('ORDER_NOT_FOUND', uuid)

    if 'auth_token' in args:
        in_auth_token = args.get('auth_token')
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
    for region in [constants.Regions.t11n_afr, constants.Regions.t11n_eu]:
        add_confirmation_if_not_present(RxConfirmation, order, region,
                                        presumed)


def received_criteria_met(order):
    if order.status != OrderStatus.sent.value:
        return False

    order_tx_confirmations = TxConfirmation.query.filter_by(
        order_id=order.id).all()
    order_rx_confirmations = RxConfirmation.query.filter_by(
        order_id=order.id).all()

    tx_confirmed_regions = set(item.region_id
                               for item in order_tx_confirmations)
    rx_confirmed_regions = set(item.region_id
                               for item in order_rx_confirmations)

    # All regions should confirm Tx
    if len(tx_confirmed_regions) < len(constants.Regions):
        return False

    # Some regions should confirm Rx
    expected_rx_confirmations = set([
        info['id'] for region, info in constants.SATELLITE_REGIONS.items()
        if info['has_receiver']
    ])
    if not (rx_confirmed_regions.issuperset(expected_rx_confirmations)):
        return False

    synthesize_presumed_rx_confirmations(order)
    order.status = OrderStatus.received.value
    db.session.commit()

    return True


def confirmation_exists(confirmations_table, order_id, region_id):
    confirmations = confirmations_table.query.filter_by(
        order_id=order_id).filter_by(region_id=region_id).all()
    if len(confirmations) > 0:
        return True
    return False


def add_confirmation_if_not_present(confirmations_table,
                                    order,
                                    region_number,
                                    presumed=False):
    region_id = constants.SATELLITE_REGIONS[constants.Regions(
        region_number)]['id']
    if not confirmation_exists(confirmations_table, order.id, region_id):
        new_confirmation = confirmations_table(order_id=order.id,
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
            func.datetime(Order.created_at) <
            datetime.datetime.utcnow() - datetime.timedelta(
                days=constants.EXPIRE_PENDING_ORDERS_AFTER_DAYS))).all()
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
            datetime.datetime.utcnow() - datetime.timedelta(
                days=constants.MESSAGE_FILE_RETENTION_TIME_DAYS))).all()
    for order in orders_to_cleanup:
        delete_message_file(order)
    return orders_to_cleanup
