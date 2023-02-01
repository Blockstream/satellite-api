import json
from datetime import datetime, timedelta

from marshmallow import fields, Schema, validate, ValidationError

from regions import all_region_numbers, region_code_to_number_list, \
    region_id_to_number
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
    regions = fields.Function(
        lambda obj: region_code_to_number_list(obj.region_code))


class AdminOrderSchema(OrderSchema):
    channel = fields.Integer()
    tx_confirmations = fields.Function(
        lambda obj:
        [region_id_to_number(x.region_id) for x in obj.tx_confirmations])
    rx_confirmations = fields.Function(
        lambda obj:
        [region_id_to_number(x.region_id) for x in obj.rx_confirmations])


def must_be_region_number(input):
    if input not in all_region_numbers:
        raise ValidationError(
            "Region number not found. The number should be one of "
            f"{all_region_numbers}.")


def must_be_region_number_list(data):
    try:
        regions_list = json.loads(data)
        if not isinstance(regions_list, list) or len(regions_list) < 1:
            raise ValidationError("Invalid json array.")
        for region_number in regions_list:
            must_be_region_number(region_number)
    except json.JSONDecodeError:
        raise ValidationError("Invalid json array.")


class OrderUploadReqSchema(Schema):
    bid = fields.Int(missing=0, validate=validate.Range(min=0))
    message = fields.Str(validate=validate.Length(
        max=constants.MAX_TEXT_MSG_LEN))
    regions = fields.String(required=False,
                            validate=must_be_region_number_list)
    channel = fields.Int(missing=constants.USER_CHANNEL,
                         validate=validate.OneOf(constants.CHANNELS))


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
    channel = fields.Int(missing=constants.USER_CHANNEL,
                         validate=validate.OneOf(constants.CHANNELS))


class TxConfirmationSchema(Schema):
    regions = fields.String(required=True, validate=must_be_region_number_list)


class RxConfirmationSchema(Schema):
    region = fields.Int(required=True, validate=must_be_region_number)


order_schema = OrderSchema()
admin_order_schema = AdminOrderSchema()
order_upload_req_schema = OrderUploadReqSchema()
order_bump_schema = OrderBumpSchema()
orders_schema = OrdersSchema()
tx_confirmation_schema = TxConfirmationSchema()
rx_confirmation_schema = RxConfirmationSchema()
