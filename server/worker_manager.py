import logging
import time

from flask import Flask
import redis

import constants
import invoice_helpers
import order_helpers
import transmitter
from database import db
from models import TxRetry
from worker import Worker

ONE_MINUTE = 60
CLEANUP_DUTY_CYCLE = 5 * ONE_MINUTE  # five minutes
ORDER_RETRANSMIT_CYCLE_SECONDS = 10


def cleanup_database(app):
    with app.app_context():
        (expired_invoices,
         expired_orders) = invoice_helpers.expire_unpaid_invoices()
        expired_orders.extend(order_helpers.expire_old_pending_orders())
        cleaned_up_orders = order_helpers.cleanup_old_message_files()

        work = [
            len(x)
            for x in [expired_invoices, expired_orders, cleaned_up_orders]
        ]
        if (any(work)):
            logging.info("Database cleanup: expired {} invoices, "
                         "{} orders, and removed {} files".format(*work))


def retry_transmission(app):
    with app.app_context():
        order_helpers.refresh_retransmission_table()
        any_retry_record = TxRetry.query.first()
        if any_retry_record:
            transmitter.tx_start()


def start_workers(app):
    cleanup_worker = Worker(period=CLEANUP_DUTY_CYCLE,
                            fcn=cleanup_database,
                            args=(app, ),
                            name="database cleaner")

    retry_worker = Worker(period=ORDER_RETRANSMIT_CYCLE_SECONDS,
                          fcn=retry_transmission,
                          args=(app, ),
                          name="order retransmission")

    cleanup_worker.thread.join()
    retry_worker.thread.join()


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{constants.DB_FILE}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config["REDIS_INSTANCE"] = redis.from_url(constants.REDIS_URI)
    db.init_app(app)
    return app


def main():
    logging.basicConfig(level=logging.DEBUG, format=constants.LOGGING_FORMAT)
    app = create_app()

    with app.app_context():
        db.create_all()
        # To avoid calling tx_start on each gunicorn worker, call it here once
        # instead. Also, wait a bit before calling tx_start so that clients
        # have enough time to reconnect to the SSE server.
        time.sleep(3)
        transmitter.tx_start()
        start_workers(app)


if __name__ == '__main__':
    main()
