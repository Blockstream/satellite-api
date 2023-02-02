import datetime
import io
import json
import os
import random
import string
from http import HTTPStatus

from database import db
from models import Invoice, Order
from utils import hmac_sha256_digest
import bidding
import constants


def rnd_string(n_bytes):
    """Generate random string with given number of bytes"""
    return ''.join(
        random.choice(string.ascii_letters + string.digits)
        for _ in range(n_bytes))


def upload_test_file(client, msg, bid, regions=[], channel=None, admin=False):
    post_data = {'bid': bid, 'file': (io.BytesIO(msg.encode()), 'testfile')}

    if len(regions) > 0:
        post_data['regions'] = [regions]
    if channel:
        post_data['channel'] = channel
    endpoint = '/admin/order' if admin else '/order'

    return client.post(endpoint,
                       data=post_data,
                       content_type='multipart/form-data')


def place_order(client,
                n_bytes,
                regions=[],
                bid=None,
                channel=None,
                admin=False):
    if bid is None:
        bid = bidding.get_min_bid(n_bytes)
    msg = rnd_string(n_bytes)
    return upload_test_file(client, msg, bid, regions, channel, admin)


def check_upload(order_uuid, expected_data):
    path = os.path.join(constants.MSG_STORE_PATH, order_uuid)
    assert os.path.exists(path)

    with open(path) as fd:
        upload_data = fd.read()
    assert upload_data == expected_data

    db_order = Order.query.filter_by(uuid=order_uuid).first()
    assert db_order is not None


def check_invoice(generated_invoice, order_uuid):
    db_order = Order.query.filter_by(uuid=order_uuid).first()
    assert db_order is not None
    db_invoice = \
        Invoice.query.filter_by(lid=generated_invoice['id']).first()
    assert db_invoice is not None
    assert db_invoice.order_id == db_order.id
    assert db_invoice.amount == db_order.unpaid_bid


def pay_invoice(invoice, client):
    charged_auth_token = hmac_sha256_digest(constants.LIGHTNING_WEBHOOK_KEY,
                                            invoice.lid)
    rv = client.post(f'/callback/{invoice.lid}/{charged_auth_token}')
    assert rv.status_code == HTTPStatus.OK


def confirm_tx(tx_seq_num, regions, client):
    tx_rv = client.post(f'/order/tx/{tx_seq_num}', data={'regions': [regions]})
    assert tx_rv.status_code == HTTPStatus.OK


def new_invoice(order_id, invoice_status, amount):
    assert (isinstance(invoice_status, constants.InvoiceStatus))
    lid = rnd_string(50)
    return Invoice(
        id=random.randint(1, 10000),
        lid=lid,
        invoice=json.dumps({
            "id":
            lid,
            "msatoshi":
            amount,
            "description":
            "BSS Test",
            "rhash":
            "94855ac3b06543",
            "payreq":
            "lntb100n1psfy",
            "expires_at":
            str(datetime.datetime.utcnow() +
                datetime.timedelta(seconds=constants.LN_INVOICE_EXPIRY)),
            "created_at":
            str(datetime.datetime.utcnow()),
            "metadata": {
                "uuid": "7f9a5b81-5358-4be0-9af6-b8c6fbac9dcd",
                "sha256_message_digest":
                "a591a6d40bf420404a011733cfb7b190d62c6"
            },
            "status":
            "unpaid"
        }),
        order_id=order_id,
        status=invoice_status.value,
        amount=amount,
        expires_at=datetime.datetime.utcnow() +
        datetime.timedelta(seconds=constants.LN_INVOICE_EXPIRY))


def generate_test_order(mock_new_invoice,
                        client,
                        order_status=None,
                        invoice_status=constants.InvoiceStatus.pending,
                        tx_seq_num=None,
                        n_bytes=500,
                        bid=None,
                        order_id=1,
                        regions=[],
                        started_transmission_at=None,
                        channel=None,
                        admin=False):
    """Generate a valid order and add it to the database

    This function generates an order with a related invoice with
    given parameters and stores them in the database.

    Args:
        mock_new_invoice: A python mock for simulation
                           orders.new_invoice function
        client: Flask client used to send api calls
        order_status: status to be set for the generated order,
                      default input valie is None but in the
                      database it will be set to pending
        invoice_status: status to be set for the generated invoice,
                        default is pending
        tx_seq_num: tx_seq_num value to be set for the generated
                    order, default value is None
        n_bytes: length of generated message
        bid: amount of bid, default value is None, if None a minimum
             valid value will be set
        order_id: the id to be used when connecting invoice to an
                  order, default value is 1
        regions: list of regions over which this order should be
            transmitted. The default value is an empty list implying
            the order should be sent over all regions.
        channel: Logical channel on which to transmit the order.
        admin: Whether to post the order via the /admin/order route.

    Returns:
        The json response of the create order endpoint.

    """
    assert (isinstance(invoice_status, constants.InvoiceStatus))

    if not bid:
        bid = bidding.get_min_bid(n_bytes)

    mock_new_invoice.return_value = (True,
                                     new_invoice(order_id, invoice_status,
                                                 bid))
    post_rv = place_order(client, n_bytes, regions, bid, channel, admin)
    assert post_rv.status_code == HTTPStatus.OK
    uuid = post_rv.get_json()['uuid']
    # Set order's sequence number and status
    db_order = Order.query.filter_by(uuid=uuid).first()

    if order_status:
        assert (isinstance(order_status, constants.OrderStatus))
        db_order.status = order_status.value

    if tx_seq_num:
        db_order.tx_seq_num = tx_seq_num

    if started_transmission_at:
        db_order.started_transmission_at = started_transmission_at

    db.session.commit()
    return post_rv.get_json()
