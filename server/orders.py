from datetime import datetime
from http import HTTPStatus
from hashlib import sha256
import json
import os
from uuid import uuid4

from flask import current_app, request, send_file
from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy import and_, or_

from constants import CHANNEL_INFO, OrderStatus
from database import db
from error import get_http_error_resp
from invoice_helpers import new_invoice, pay_invoice
from models import Order, RxConfirmation, TxConfirmation
from regions import region_number_list_to_code
from schemas import admin_order_schema, order_schema, orders_schema,\
    order_upload_req_schema, order_bump_schema,\
    rx_confirmation_schema, tx_confirmation_schema
import bidding
import constants
import order_helpers
import transmitter

SHA256_BLOCK_SIZE = 65536


def sha256_checksum(filename, block_size=SHA256_BLOCK_SIZE):
    msg_hash = sha256()
    with open(filename, 'rb') as f:
        for block in iter(lambda: f.read(block_size), b''):
            msg_hash.update(block)
    return msg_hash.hexdigest()


class OrderResource(Resource):

    def get(self, uuid):
        admin_mode = request.path.startswith("/admin/")

        success, order_or_error = order_helpers.get_and_authenticate_order(
            uuid, request.form, request.args)
        if not success:
            return order_or_error
        order = order_or_error

        if not admin_mode and 'get' not in \
                constants.CHANNEL_INFO[order.channel].user_permissions:
            return get_http_error_resp('ORDER_CHANNEL_UNAUTHORIZED_OP',
                                       order.channel)
        schema = admin_order_schema if admin_mode else order_schema
        return schema.dump(order)

    def delete(self, uuid):
        admin_mode = request.path.startswith("/admin/")

        success, order_or_error = order_helpers.get_and_authenticate_order(
            uuid, request.form, request.args)
        if not success:
            return order_or_error
        order = order_or_error

        if not admin_mode and 'delete' not in \
                constants.CHANNEL_INFO[order.channel].user_permissions:
            return get_http_error_resp('ORDER_CHANNEL_UNAUTHORIZED_OP',
                                       order.channel)

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
        admin_mode = request.path.startswith("/admin/")

        try:
            args = order_upload_req_schema.load(request.form)
        except ValidationError as error:
            return error.messages, HTTPStatus.BAD_REQUEST

        has_msg = 'message' in args
        has_file = 'file' in request.files

        channel = args['channel']
        if not admin_mode and 'post' not in \
                constants.CHANNEL_INFO[channel].user_permissions:
            return get_http_error_resp('ORDER_CHANNEL_UNAUTHORIZED_OP',
                                       channel)
        requires_payment = CHANNEL_INFO[channel].requires_payment

        if (has_msg and has_file):
            return "Choose message or file", HTTPStatus.BAD_REQUEST

        if (not (has_msg or has_file)):
            return get_http_error_resp('MESSAGE_MISSING')

        uuid = str(uuid4())
        filepath = os.path.join(constants.MSG_STORE_PATH, uuid)

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

        if (msg_size > constants.CHANNEL_INFO[channel].max_msg_size):
            os.remove(filepath)
            return get_http_error_resp(
                'MESSAGE_FILE_TOO_LARGE',
                constants.CHANNEL_INFO[channel].max_msg_size / (2**20))

        bid = int(args.get('bid')) if requires_payment else 0
        if (requires_payment and not bidding.validate_bid(msg_size, bid)):
            os.remove(filepath)
            min_bid = bidding.get_min_bid(msg_size)
            return get_http_error_resp('BID_TOO_SMALL', min_bid)

        msg_digest = sha256_checksum(filepath)
        starting_state = OrderStatus.pending.value if requires_payment \
            else OrderStatus.paid.value
        new_order = Order(uuid=uuid,
                          unpaid_bid=bid,
                          message_size=msg_size,
                          message_digest=msg_digest,
                          status=starting_state,
                          channel=channel)

        if requires_payment:
            success, invoice = new_invoice(new_order, bid)
            if not success:
                return invoice
            new_order.invoices.append(invoice)

        if 'regions' in args:
            regions_in_request = json.loads(args['regions'])
            new_order.region_code = region_number_list_to_code(
                regions_in_request)

        db.session.add(new_order)
        db.session.commit()

        if constants.FORCE_PAYMENT and requires_payment:
            current_app.logger.info('force payment of the invoice')
            pay_invoice(invoice)
            transmitter.tx_start(new_order.channel)
        elif not requires_payment:
            transmitter.tx_start(new_order.channel)

        # Return the invoice only if the channel requires payment for orders
        resp = {
            'auth_token': order_helpers.compute_auth_token(uuid),
            'uuid': uuid
        }
        if requires_payment:
            resp['lightning_invoice'] = json.loads(invoice.invoice)

        return resp


class BumpOrderResource(Resource):

    def post(self, uuid):
        query_args = request.args
        try:
            form_args = order_bump_schema.load(request.form)
        except ValidationError as error:
            return error.messages, HTTPStatus.BAD_REQUEST

        success, order_or_error = order_helpers.get_and_authenticate_order(
            uuid, form_args, query_args)
        if not success:
            return order_or_error
        order = order_or_error

        if not CHANNEL_INFO[order.channel].requires_payment:
            return get_http_error_resp('ORDER_CHANNEL_UNAUTHORIZED_OP',
                                       order.channel)

        if order.status != OrderStatus.pending.value and\
           order.status != OrderStatus.paid.value:
            return get_http_error_resp('ORDER_BUMP_ERROR',
                                       OrderStatus(order.status).name)

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
        admin_mode = request.path.startswith("/admin/")
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
        channel = args['channel']

        if not admin_mode and 'get' not in \
                constants.CHANNEL_INFO[channel].user_permissions:
            return get_http_error_resp('ORDER_CHANNEL_UNAUTHORIZED_OP',
                                       channel)

        if state == 'pending':
            orders = Order.query.filter(and_(
                Order.channel == channel,
                Order.status == OrderStatus[state].value)).\
                filter(db.func.datetime(Order.created_at) < before).\
                order_by(Order.created_at.desc()).\
                limit(limit)
        elif state == 'queued':
            orders = Order.query.filter(and_(Order.channel == channel, or_(
                Order.status ==
                OrderStatus.transmitting.value,
                Order.status ==
                OrderStatus.confirming.value,
                Order.status ==
                OrderStatus.paid.value))).\
                filter(db.func.datetime(Order.created_at) < before).\
                order_by(Order.bid_per_byte.desc()).limit(limit)
        elif state == 'sent':
            orders = Order.query.filter(and_(Order.channel == channel, or_(
                Order.status ==
                OrderStatus.sent.value,
                Order.status ==
                OrderStatus.received.value))).\
                filter(db.func.datetime(Order.created_at) < before).\
                order_by(Order.ended_transmission_at.desc()).\
                limit(limit)

        return [order_schema.dump(order) for order in orders]


class GetMessageResource(Resource):

    def get(self, uuid):
        order = Order.query.filter_by(uuid=uuid).filter(
            or_(Order.status == OrderStatus.sent.value,
                Order.status == OrderStatus.transmitting.value,
                Order.status == OrderStatus.confirming.value)).first()
        if not order:
            return get_http_error_resp('ORDER_NOT_FOUND', uuid)

        message_path = os.path.join(constants.MSG_STORE_PATH, uuid)
        return send_file(message_path,
                         mimetype='application/json',
                         as_attachment=True,
                         add_etags=False)


class GetMessageBySeqNumResource(Resource):

    def get(self, tx_seq_num):
        admin_mode = request.path.startswith("/admin/")

        order = Order.query.filter_by(tx_seq_num=tx_seq_num).filter(
            or_(Order.status == OrderStatus.sent.value,
                Order.status == OrderStatus.transmitting.value,
                Order.status == OrderStatus.confirming.value,
                Order.status == OrderStatus.received.value)).first()
        if not order:
            return get_http_error_resp('SEQUENCE_NUMBER_NOT_FOUND', tx_seq_num)

        if not admin_mode and 'get' not in \
                constants.CHANNEL_INFO[order.channel].user_permissions:
            return get_http_error_resp('ORDER_CHANNEL_UNAUTHORIZED_OP',
                                       order.channel)

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

        # Find order by sequence number. Note only orders in the following
        # states have a sequence number: transmitting, confirming, sent or
        # received. In contrast, pending or paid orders do not have a sequence
        # number. Hence, the following query implicitly ensures the order is in
        # a reasonable state to receive a Tx confirmation, even if it's a
        # repeated confirmation (e.g., if the order is already received).
        order = Order.query.filter_by(tx_seq_num=tx_seq_num).first()
        if not order:
            return get_http_error_resp('SEQUENCE_NUMBER_NOT_FOUND', tx_seq_num)

        # A Tx confirmation indicates that at least one Tx host finished
        # transmitting the order. At this point, the other Tx hosts should
        # complete the order soon. In the meantime, change the order state
        # from transmitting to confirming so that other pending orders
        # can be unblocked.
        last_status = order.status
        if order.status == OrderStatus.transmitting.value:
            order.status = OrderStatus.confirming.value
            db.session.commit()

        regions_in_request = json.loads(args['regions'])
        for region_number in regions_in_request:
            order_helpers.add_confirmation_if_not_present(
                TxConfirmation, order, region_number)

        # Check whether the order is in "sent" or "received" state already. In
        # the positive case, end the current transmission to start a new one.
        if order_helpers.sent_or_received_criteria_met(order):
            transmitter.tx_end(order)

        # If the order status is still "confirming" at this point, it can be
        # inferred that tx_end() was not called above. Consequently, we have
        # not released any blocked orders yet. Nevertheless, we can do so now,
        # since the current order is already being confirmed. Go ahead and call
        # tx_start to unblock any orders waiting on the present order.
        #
        # Also, if the incoming confirmation is not the first for the present
        # order, the "last_status" value was already "confirming". In this
        # case, we have already attempted to release blocked orders in a
        # previous call, so there is no need to call tx_start() again.
        db.session.refresh(order)
        if order.status == OrderStatus.confirming.value and \
                last_status == OrderStatus.transmitting.value:
            transmitter.tx_start(order.channel)

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

        region_in_request = int(args['region'])
        order_helpers.add_confirmation_if_not_present(RxConfirmation, order,
                                                      region_in_request)

        # Check whether the order is in "sent" or "received" state already. In
        # the positive case, end the current transmission to start a new one.
        if order_helpers.sent_or_received_criteria_met(order):
            transmitter.tx_end(order)

        return {
            'message': f'reception confirmed for region {region_in_request}'
        }
