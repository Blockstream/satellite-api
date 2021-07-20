import datetime
import logging
import time

import redis
from flask import current_app

import constants
from database import db
from models import Order
from schemas import order_schema


class TxEngine:
    def __init__(self):
        self.redis = redis.from_url(current_app.config.get("REDIS_URL"))

    def assign_tx_seq_num(self, order):
        """Assign Tx sequence number to order"""
        last_tx_order = Order.query.order_by(Order.tx_seq_num.desc()).first()

        if last_tx_order.tx_seq_num:
            order.tx_seq_num = last_tx_order.tx_seq_num + 1
        else:
            order.tx_seq_num = 1
        db.session.commit()

    def publish_to_sse_server(self, order):
        msg = order_schema.dumps(order)
        self.redis.publish(channel=constants.SUB_CHANNELS[0], message=msg)
        return

    def tx_start(self, order):
        """Start transmission"""
        if order.status == constants.OrderStatus.paid.value:
            logging.info(f'transmission start {order.uuid}')
            self.assign_tx_seq_num(order)
            order.status = constants.OrderStatus.transmitting.value
            order.started_transmission_at = datetime.datetime.utcnow()
            db.session.commit()
            self.publish_to_sse_server(order)

    def tx_end(self, order):
        """End transmission"""
        if order.status == constants.OrderStatus.transmitting.value:
            logging.info(f'transmission end {order.uuid}')
            order.status = constants.OrderStatus.sent.value
            order.ended_transmission_at = datetime.datetime.utcnow()
            db.session.commit()
            self.publish_to_sse_server(order)

    def tx_resume(self):
        """Resume interrupted transmissions"""
        orders = Order.query.filter_by(
            status=constants.OrderStatus.transmitting.value).all()
        for order in orders:
            logging.info(f'resuming interrupted transmission {order.uuid}')
            self.tx_end(order)

    # rounds = -1 means run forever and is the default value. Values other than
    # -1 are mainly used from tests.
    def start(self, rounds=-1):
        logging.info("Starting transmitter")
        round_count = 0
        self.tx_resume()

        while True:
            sendable_order = None
            while sendable_order is None:
                # Look for an elligble order to transmit and, if one is found,
                # begin transmitting it.
                sendable_order = Order.query.filter_by(
                    status=constants.OrderStatus.paid.value).order_by(
                        Order.bid_per_byte.desc()).first()
                if sendable_order:
                    self.tx_start(sendable_order)
                else:
                    time.sleep(1.0)

            if constants.TRANSMIT_RATE:
                transmit_time = \
                    sendable_order.message_size / constants.TRANSMIT_RATE
                logging.info(f'sleeping for {transmit_time} while \
                        {sendable_order.uuid} transmits')
                time.sleep(transmit_time)

            self.tx_end(sendable_order)
            if rounds > -1:
                round_count += 1
                if round_count >= rounds:
                    return
