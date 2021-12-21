import logging

from flask import Flask
import redis

import constants
import invoice_helpers
import order_helpers
import transmitter
from database import db
from worker import Worker

ONE_MINUTE = 60
CLEANUP_DUTY_CYCLE = 5 * ONE_MINUTE  # five minutes


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


def start_workers(app):
    # Workers
    cleanup_worker = Worker(period=CLEANUP_DUTY_CYCLE,
                            fcn=cleanup_database,
                            args=(app, ),
                            name="database cleaner")

    cleanup_worker.thread.join()


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
        # In order to avoid running resume/start on each gunicorn worker, these
        # calls are being made from this module only instead of the main server
        transmitter.tx_resume()
        transmitter.tx_start()
        start_workers(app)


if __name__ == '__main__':
    main()
