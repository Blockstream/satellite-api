import datetime
import logging

from flask import current_app

import constants
from database import db
from models import Order
from schemas import order_schema


def assign_tx_seq_num(order):
    """Assign Tx sequence number to order"""
    last_tx_order = Order.query.order_by(Order.tx_seq_num.desc()).first()

    if last_tx_order.tx_seq_num:
        order.tx_seq_num = last_tx_order.tx_seq_num + 1
    else:
        order.tx_seq_num = 1
    db.session.commit()


def redis():
    return current_app.config.get("REDIS_INSTANCE")


def publish_to_sse_server(order):
    msg = order_schema.dumps(order)
    redis().publish(channel=constants.SUB_CHANNELS[0], message=msg)
    return


def tx_start():
    # Do not start a new transmission if another order is
    # being transmitted right now
    transmitting_orders = Order.query.filter_by(
        status=constants.OrderStatus.transmitting.value).all()
    if transmitting_orders:
        return
    # Pick the order with the highest bid and start transmission
    order = Order.query.filter_by(
        status=constants.OrderStatus.paid.value).order_by(
            Order.bid_per_byte.desc()).first()
    if order:
        logging.info(f'transmission start {order.uuid}')
        assign_tx_seq_num(order)
        order.status = constants.OrderStatus.transmitting.value
        order.started_transmission_at = datetime.datetime.utcnow()
        db.session.commit()
        publish_to_sse_server(order)


def tx_end(order):
    """End transmission"""
    if order.status == constants.OrderStatus.transmitting.value:
        logging.info(f'transmission end {order.uuid}')
        order.status = constants.OrderStatus.sent.value
        order.ended_transmission_at = datetime.datetime.utcnow()
        db.session.commit()
        publish_to_sse_server(order)
        # Start the next queued order as soon as the current order finishes
        tx_start()


def tx_resume():
    """Resume interrupted transmissions"""
    orders = Order.query.filter_by(
        status=constants.OrderStatus.transmitting.value).all()
    for order in orders:
        logging.info(f'resuming interrupted transmission {order.uuid}')
        tx_end(order)
