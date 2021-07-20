import logging

from flask import Flask

import constants
import invoice_helpers
import order_helpers
from database import db
from transmitter import TxEngine
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


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{constants.DB_FILE}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config["REDIS_URL"] = constants.REDIS_URI
    db.init_app(app)
    with app.app_context():
        db.create_all()
    return app


def main():
    logging.basicConfig(level=logging.DEBUG, format=constants.LOGGING_FORMAT)
    app = create_app()

    # Workers
    Worker(period=CLEANUP_DUTY_CYCLE,
           fcn=cleanup_database,
           args=(app, ),
           name="database cleaner")

    # Main Tx Engine
    with app.app_context():
        tx_engine = TxEngine()
        tx_engine.start()


if __name__ == '__main__':
    main()
