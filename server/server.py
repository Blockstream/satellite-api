import os
import shutil
import logging

from flask import Flask
from flask_restful import Api

import constants
from database import db
from info import InfoResource
from invoices import InvoiceResource
from orders import BumpOrderResource, GetMessageResource,\
    GetMessageBySeqNumResource, OrderResource, OrdersResource,\
    OrderUploadResource, RxConfirmationResource, TxConfirmationResource
from queues import QueueResource


def create_app(from_test=False):
    if not os.path.isdir(constants.MSG_STORE_PATH):
        os.makedirs(constants.MSG_STORE_PATH)

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{constants.DB_FILE}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TESTING'] = from_test
    app.config["REDIS_URL"] = constants.REDIS_URI

    db.init_app(app)
    with app.app_context():
        db.create_all()
    api = Api(app)
    api.add_resource(OrderUploadResource, '/order')
    api.add_resource(OrdersResource, '/orders/<state>')
    api.add_resource(OrderResource, '/order/<uuid>')
    api.add_resource(BumpOrderResource, '/order/<uuid>/bump')
    api.add_resource(TxConfirmationResource, '/order/tx/<tx_seq_num>')
    api.add_resource(RxConfirmationResource, '/order/rx/<tx_seq_num>')
    api.add_resource(InfoResource, '/info')
    api.add_resource(InvoiceResource, '/callback/<lid>/<charged_auth_token>')
    api.add_resource(GetMessageBySeqNumResource, '/message/<tx_seq_num>')
    api.add_resource(QueueResource, '/queue.html')

    if constants.env == 'development' or constants.env == 'test':
        api.add_resource(GetMessageResource, '/order/<uuid>/sent_message')

    logging.basicConfig(level=logging.DEBUG, format=constants.LOGGING_FORMAT)
    return app


def teardown_app(app):
    if (app.config['TESTING']):
        shutil.rmtree(constants.MSG_STORE_PATH)
        os.remove(constants.DB_FILE)


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=constants.SERVER_PORT)