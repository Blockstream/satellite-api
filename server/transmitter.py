import json
import logging
from datetime import datetime

from flask import current_app
from sqlalchemy import and_

import constants
import order_helpers
from database import db
from models import Order, TxRetry
from regions import region_code_to_number_list
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


def publish_to_sse_server(order, retransmit_info=None):
    msg = order_schema.dump(order)
    # If it's a retransmission, take the regions list from the tx_retries table
    # instead of the orders table.
    if retransmit_info:
        msg['regions'] = region_code_to_number_list(
            retransmit_info.region_code)
    msg = json.dumps(msg)
    redis().publish(channel=constants.CHANNEL_INFO[order.channel].name,
                    message=msg)
    return


def tx_start(channel=None):
    """Look for pending transmissions and serve them

    An order is ready for transmission when already paid or when being
    retransmitted. Also, a pending transmission can only be served if there is
    no other ongoing transmission on the logical channel. Each channel can only
    serve one transmission at a time.

    This function works both for a single defined channel or for all channels.
    When the channel parameter is undefined, it looks for pending transmissions
    in all channels. Otherwise, it processes the specified channel only.

    Args:
        channel (int, optional): Logical transmission channel to serve.
            Defaults to None.

    """
    # Call itself recursively if the channel is not defined
    if (channel is None):
        for channel in constants.CHANNELS:
            tx_start(channel)
        return

    transmitting_orders = Order.query.filter(
        and_(Order.status == constants.OrderStatus.transmitting.value,
             Order.channel == channel)).all()

    # Do not start a new transmission if another order is being transmitted
    # right now
    if len(transmitting_orders) > 0:
        return

    # First, try to find a paid order with the highest bid in the orders table
    # and start its transmission. If no paid orders are found there, look into
    # the tx_retries table and retransmit one of the orders from there if it
    # meets the retransmission criteria
    order = Order.query.filter(
        and_(Order.status == constants.OrderStatus.paid.value,
             Order.channel == channel)).order_by(
                 Order.bid_per_byte.desc()).first()

    if order:
        logging.info(f'transmission start {order.uuid}')
        assign_tx_seq_num(order)
        order.status = constants.OrderStatus.transmitting.value
        order.started_transmission_at = datetime.utcnow()
        db.session.commit()
        publish_to_sse_server(order)
    else:
        # No order found for the first transmission.
        # Check if any order requires retransmission.
        order, retransmit_info = order_helpers.get_next_retransmission(channel)
        if order and retransmit_info:
            logging.info(f'retransmission start {order.uuid}')
            order.status = constants.OrderStatus.transmitting.value
            retransmit_info.retry_count += 1
            retransmit_info.last_attempt = datetime.utcnow()
            retransmit_info.pending = False
            db.session.commit()
            publish_to_sse_server(order, retransmit_info)


def tx_end(order):
    """End transmission"""
    if order.ended_transmission_at is None:
        logging.info(f'transmission end {order.uuid}')
        order.ended_transmission_at = datetime.utcnow()
        retransmit_info = TxRetry.query.filter_by(order_id=order.id).first()
        # Cleanup the TxRetry
        TxRetry.query.filter_by(order_id=order.id).delete()
        db.session.commit()
        publish_to_sse_server(order, retransmit_info)
        # Start the next queued order as soon as the current order finishes
        tx_start(order.channel)
