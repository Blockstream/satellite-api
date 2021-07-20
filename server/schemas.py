import json
from datetime import datetime, timedelta

from marshmallow import fields, Schema, validate, validates, ValidationError

import constants


class OrderSchema(Schema):
    uuid = fields.String()
    bid = fields.Integer()
    message_size = fields.Integer()
    bid_per_byte = fields.Float()
    message_digest = fields.String()
    status = fields.Function(
        lambda obj: constants.OrderStatus(obj.status).name)
    created_at = fields.DateTime()
    cancelled_at = fields.DateTime()
    started_transmission_at = fields.DateTime()
    ended_transmission_at = fields.DateTime()
    tx_seq_num = fields.Integer()
    unpaid_bid = fields.Integer()


class OrderUploadReqSchema(Schema):
    bid = fields.Int(required=True, validate=validate.Range(min=0))
    message = fields.Str(validate=validate.Length(
        max=constants.MAX_TEXT_MSG_LEN))


class OrderBumpSchema(Schema):
    uuid = fields.String()
    bid_increase = fields.Int(required=True, validate=validate.Range(min=0))
    auth_token = fields.Str()


class OrdersSchema(Schema):
    # When 'before' parameter is missing, set it to a time in near
    # future (e.g. 5 seconds from now) to make sure none of the
    # existing orders get filtered
    before = fields.DateTime(
        missing=lambda: datetime.utcnow() + timedelta(seconds=5), format='iso')
    limit = fields.Int(missing=lambda: constants.PAGE_SIZE,
                       validate=validate.Range(min=1,
                                               max=constants.MAX_PAGE_SIZE))


class TxConfirmationSchema(Schema):
    regions = fields.String(required=True)

    @validates('regions')
    def must_be_json_array(self, data):
        try:
            js = json.loads(data)
            if not isinstance(js, list) or len(js) < 1:
                raise ValidationError("Invalid json array.")
        except json.JSONDecodeError:
            raise ValidationError("Invalid json array.")


class RxConfirmationSchema(Schema):
    region = fields.Int(required=True)


order_schema = OrderSchema()
order_upload_req_schema = OrderUploadReqSchema()
order_bump_schema = OrderBumpSchema()
orders_schema = OrdersSchema()
tx_confirmation_schema = TxConfirmationSchema()
rx_confirmation_schema = RxConfirmationSchema()
