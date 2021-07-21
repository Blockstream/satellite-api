from datetime import datetime
from http import HTTPStatus
from hashlib import sha256
import json
import os
from uuid import uuid4

from flask import current_app, request, send_file

from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy import or_

from constants import OrderStatus, Regions
from database import db
from error import get_http_error_resp
from invoice_helpers import new_invoice, pay_invoice
from models import Order, RxConfirmation, TxConfirmation
from schemas import order_schema, orders_schema,\
    order_upload_req_schema, order_bump_schema,\
    rx_confirmation_schema, tx_confirmation_schema
import bidding
import constants
import order_helpers

SHA256_BLOCK_SIZE = 65536


def sha256_checksum(filename, block_size=SHA256_BLOCK_SIZE):
    msg_hash = sha256()
    with open(filename, 'rb') as f:
        for block in iter(lambda: f.read(block_size), b''):
            msg_hash.update(block)
    return msg_hash.hexdigest()


class OrderResource(Resource):
    def get(self, uuid):
        success, order_or_error = order_helpers.get_and_authenticate_order(
            uuid, request.form, request.args)
        if not success:
            return order_or_error
        order = order_or_error
        return order_schema.dump(order)

    def delete(self, uuid):
        success, order_or_error = order_helpers.get_and_authenticate_order(
            uuid, request.form, request.args)
        if not success:
            return order_or_error
        order = order_or_error

        if order.status != OrderStatus.pending.value and\
           order.status != OrderStatus.paid.value:
            return get_http_error_resp('ORDER_CANCELLATION_ERROR',
                                       OrderStatus(order.status).name)

        message_file = os.path.join(constants.MSG_STORE_PATH, order.uuid)
        if os.path.exists(message_file):
            os.remove(message_file)
        order.status = OrderStatus.cancelled.value
        order.cancelled_at = datetime.utcnow()
        db.session.commit()
        return {"message": "order cancelled"}


class OrderUploadResource(Resource):
    def post(self):
        args = request.form
        errors = order_upload_req_schema.validate(args)

        if errors:
            return errors, HTTPStatus.BAD_REQUEST

        has_msg = 'message' in args
        has_file = 'file' in request.files

        if (has_msg and has_file):
            return "Choose message or file", HTTPStatus.BAD_REQUEST

        if (not (has_msg or has_file)):
            return get_http_error_resp('MESSAGE_MISSING')

        uuid = str(uuid4())
        filepath = os.path.join(constants.MSG_STORE_PATH, uuid)
        bid = int(args.get('bid'))

        if (has_msg):
            with open(filepath, 'w') as fd:
                fd.write(args['message'])
        else:
            file = request.files['file']
            file.save(filepath)

        msg_size = os.stat(filepath).st_size

        if (msg_size < constants.MIN_MESSAGE_SIZE):
            os.remove(filepath)
            return get_http_error_resp('MESSAGE_FILE_TOO_SMALL',
                                       constants.MIN_MESSAGE_SIZE)

        if (msg_size > constants.MAX_MESSAGE_SIZE):
            os.remove(filepath)
            return get_http_error_resp('MESSAGE_FILE_TOO_LARGE',
                                       constants.MAX_MESSAGE_SIZE / (2**20))

        if (not bidding.validate_bid(msg_size, bid)):
            os.remove(filepath)
            min_bid = bidding.get_min_bid(msg_size)
            return get_http_error_resp('BID_TOO_SMALL', min_bid)

        msg_digest = sha256_checksum(filepath)
        new_order = Order(uuid=uuid,
                          unpaid_bid=bid,
                          message_size=msg_size,
                          message_digest=msg_digest,
                          status=OrderStatus.pending.value)

        success, invoice = new_invoice(new_order, bid)
        if not success:
            return invoice

        new_order.invoices.append(invoice)
        db.session.add(new_order)
        db.session.commit()

        if constants.FORCE_PAYMENT:
            current_app.logger.info('force payment of the invoice')
            pay_invoice(invoice)

        return {
            'auth_token': order_helpers.compute_auth_token(uuid),
            'uuid': uuid,
            'lightning_invoice': json.loads(invoice.invoice)
        }


class BumpOrderResource(Resource):
    def post(self, uuid):
        query_args = request.args
        form_args = request.form
        errors = order_bump_schema.validate(form_args)

        if errors:
            return errors, HTTPStatus.BAD_REQUEST

        success, order_or_error = order_helpers.get_and_authenticate_order(
            uuid, form_args, query_args)
        if not success:
            return order_or_error
        order = order_or_error

        success, invoice = new_invoice(order, form_args['bid_increase'])
        if not success:
            return invoice

        order.invoices.append(invoice)
        order_helpers.adjust_bids(order)
        db.session.commit()

        return {
            'auth_token': order_helpers.compute_auth_token(uuid),
            'uuid': uuid,
            'lightning_invoice': json.loads(invoice.invoice)
        }


class OrdersResource(Resource):
    def get(self, state):
        if state not in ['pending', 'queued', 'sent']:
            return {
                state: [
                    f'The requested queue of {state} orders\
                does not exist'
                ]
            }, HTTPStatus.NOT_FOUND

        try:
            args = orders_schema.load(request.args)
        except ValidationError as error:
            return error.messages, HTTPStatus.BAD_REQUEST

        before = db.func.datetime(args['before'])
        limit = args['limit']

        if state == 'pending':
            orders = Order.query.filter_by(
                status=OrderStatus[state].value).\
                filter(db.func.datetime(Order.created_at) < before).\
                order_by(Order.created_at.desc()).\
                limit(limit)
        elif state == 'queued':
            orders = Order.query.filter(or_(
                Order.status ==
                OrderStatus.pending.value,
                Order.status ==
                OrderStatus.transmitting.value)).\
                filter(db.func.datetime(Order.created_at) < before).\
                order_by(Order.bid_per_byte.desc()).limit(limit)
        elif state == 'sent':
            orders = Order.query.filter(or_(
                Order.status ==
                OrderStatus.sent.value,
                Order.status ==
                OrderStatus.received.value)).\
                filter(db.func.datetime(Order.created_at) < before).\
                order_by(Order.ended_transmission_at.desc()).\
                limit(limit)

        return [order_schema.dump(order) for order in orders]


class GetMessageResource(Resource):
    def get(self, uuid):
        order = Order.query.filter_by(uuid=uuid).filter(
            or_(Order.status == OrderStatus.sent.value,
                Order.status == OrderStatus.transmitting.value)).first()
        if not order:
            return get_http_error_resp('ORDER_NOT_FOUND', uuid)

        message_path = os.path.join(constants.MSG_STORE_PATH, uuid)
        return send_file(message_path,
                         mimetype='application/json',
                         as_attachment=True,
                         add_etags=False)


class GetMessageBySeqNumResource(Resource):
    def get(self, tx_seq_num):
        order = Order.query.filter_by(tx_seq_num=tx_seq_num).filter(
            or_(Order.status == OrderStatus.sent.value,
                Order.status == OrderStatus.transmitting.value,
                Order.status == OrderStatus.received.value)).first()
        if not order:
            return get_http_error_resp('SEQUENCE_NUMBER_NOT_FOUND', tx_seq_num)

        message_path = os.path.join(constants.MSG_STORE_PATH, order.uuid)
        return send_file(message_path,
                         mimetype='application/json',
                         as_attachment=True,
                         add_etags=False)


class TxConfirmationResource(Resource):
    def post(self, tx_seq_num):
        args = request.form
        errors = tx_confirmation_schema.validate(args)

        if errors:
            return errors, HTTPStatus.BAD_REQUEST

        order = Order.query.filter_by(tx_seq_num=tx_seq_num).first()
        if not order:
            return get_http_error_resp('SEQUENCE_NUMBER_NOT_FOUND', tx_seq_num)

        all_region_numbers = set(item.value for item in Regions)

        regions_in_request = json.loads(args['regions'])
        for region_number in regions_in_request:
            if region_number not in all_region_numbers:
                return get_http_error_resp('REGION_NOT_FOUND', region_number)
            order_helpers.add_confirmation_if_not_present(
                TxConfirmation, order, region_number)

        order_helpers.received_criteria_met(order)

        return {
            'message': f'transmission confirmed for regions {args["regions"]}'
        }


class RxConfirmationResource(Resource):
    def post(self, tx_seq_num):
        args = request.form
        errors = rx_confirmation_schema.validate(args)

        if errors:
            return errors, HTTPStatus.BAD_REQUEST

        order = Order.query.filter_by(tx_seq_num=tx_seq_num).first()
        if not order:
            return get_http_error_resp('SEQUENCE_NUMBER_NOT_FOUND', tx_seq_num)

        all_region_numbers = set(item.value for item in Regions)

        region_in_request = int(args['region'])
        if region_in_request not in all_region_numbers:
            return get_http_error_resp('REGION_NOT_FOUND', region_in_request)
        order_helpers.add_confirmation_if_not_present(RxConfirmation, order,
                                                      region_in_request)

        order_helpers.received_criteria_met(order)

        return {
            'message': f'reception confirmed for region {region_in_request}'
        }
