import pytest
from http import HTTPStatus
from unittest.mock import patch

from database import db
from constants import InvoiceStatus, OrderStatus
from error import assert_error
from models import Invoice, Order
from utils import hmac_sha256_digest
import bidding
import constants
import server

from common import new_invoice, \
    place_order, rnd_string, upload_test_file


@pytest.fixture
def client(mockredis):
    app = server.create_app(from_test=True)
    app.app_context().push()
    with app.test_client() as client:
        yield client
    server.teardown_app(app)


def test_paid_invoice_callback_parameter_validation(client):
    rv = client.post('/callback')
    assert rv.status_code == HTTPStatus.NOT_FOUND

    rv = client.post('/callback/test_lid')
    assert rv.status_code == HTTPStatus.NOT_FOUND

    rv = client.get('/callback/test_lid/test_auth_token')
    assert rv.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@patch('orders.new_invoice')
def test_paid_invoice_callback_invalid_input(mock_new_invoice, client):
    n_bytes = 500
    invoice = new_invoice(1, InvoiceStatus.paid, bidding.get_min_bid(n_bytes))
    mock_new_invoice.return_value = (True, invoice)
    post_rv = place_order(client, n_bytes)
    assert post_rv.status_code == HTTPStatus.OK

    charged_auth_token = hmac_sha256_digest(constants.LIGHTNING_WEBHOOK_KEY,
                                            invoice.lid)
    # invalid lid
    rv = client.post(f'/callback/some_text/{charged_auth_token}')
    assert rv.status_code == HTTPStatus.NOT_FOUND

    # invalid auth token
    rv = client.post(f'/callback/{invoice.lid}/some_text')
    assert rv.status_code == HTTPStatus.UNAUTHORIZED


@patch('orders.new_invoice')
def test_paid_invoice_callback_orphaned_invoice(mock_new_invoice, client):
    n_bytes = 500
    invoice = new_invoice(1, InvoiceStatus.paid, bidding.get_min_bid(n_bytes))
    mock_new_invoice.return_value = (True, invoice)
    post_rv = place_order(client, n_bytes)
    assert post_rv.status_code == HTTPStatus.OK

    db_invoice = Invoice.query.filter_by(order_id=1).first()
    # nullify the order_id of an invoice to mimic an orphaned invoice
    db_invoice.order_id = None
    db.session.commit()

    charged_auth_token = hmac_sha256_digest(constants.LIGHTNING_WEBHOOK_KEY,
                                            invoice.lid)

    rv = client.post(f'/callback/{invoice.lid}/{charged_auth_token}')
    assert rv.status_code == HTTPStatus.NOT_FOUND
    assert_error(rv.get_json(), 'ORPHANED_INVOICE')


@patch('orders.new_invoice')
def test_paid_invoice_callback_pay_twice(mock_new_invoice, client):
    n_bytes = 500
    invoice = new_invoice(1, InvoiceStatus.paid, bidding.get_min_bid(n_bytes))
    mock_new_invoice.return_value = (True, invoice)
    post_rv = place_order(client, n_bytes)
    assert post_rv.status_code == HTTPStatus.OK

    charged_auth_token = hmac_sha256_digest(constants.LIGHTNING_WEBHOOK_KEY,
                                            invoice.lid)
    rv = client.post(f'/callback/{invoice.lid}/{charged_auth_token}')
    assert rv.status_code == HTTPStatus.BAD_REQUEST
    assert_error(rv.get_json(), 'INVOICE_ALREADY_PAID')


@patch('orders.new_invoice')
def test_paid_invoice_callback_successfully(mock_new_invoice, client):
    n_bytes = 500
    invoice = new_invoice(1, InvoiceStatus.pending,
                          bidding.get_min_bid(n_bytes))
    mock_new_invoice.return_value = (True, invoice)
    post_rv = place_order(client, n_bytes)
    uuid_order = post_rv.get_json()['uuid']
    assert post_rv.status_code == HTTPStatus.OK

    charged_auth_token = hmac_sha256_digest(constants.LIGHTNING_WEBHOOK_KEY,
                                            invoice.lid)
    rv = client.post(f'/callback/{invoice.lid}/{charged_auth_token}')
    assert rv.status_code == HTTPStatus.OK

    # refetch the order and the invoice from the database
    db_invoice = Invoice.query.filter_by(lid=invoice.lid).first()
    db_order = Order.query.filter_by(uuid=uuid_order).first()
    assert db_invoice.status == InvoiceStatus.paid.value
    assert db_order.status == OrderStatus.transmitting.value
    assert db_invoice.paid_at is not None


@patch('orders.new_invoice')
def test_pay_multiple_invoices(mock_new_invoice, client):
    n_bytes = 500
    first_bid = 1000
    total_bid = first_bid
    msg = rnd_string(n_bytes)
    invoice1 = new_invoice(1, InvoiceStatus.pending, first_bid)
    charged_auth_token1 = hmac_sha256_digest(constants.LIGHTNING_WEBHOOK_KEY,
                                             invoice1.lid)
    mock_new_invoice.return_value = (True, invoice1)

    rv = upload_test_file(client, msg, first_bid)
    assert rv.status_code == HTTPStatus.OK
    post_json_resp = rv.get_json()
    uuid = post_json_resp['uuid']
    auth_token = post_json_resp['auth_token']

    # Bump the bid on the existing order
    second_bid = 2000
    total_bid += second_bid
    invoice2 = new_invoice(1, InvoiceStatus.pending, second_bid)
    charged_auth_token2 = hmac_sha256_digest(constants.LIGHTNING_WEBHOOK_KEY,
                                             invoice2.lid)
    mock_new_invoice.return_value = (True, invoice2)
    bump_rv = client.post(f'/order/{uuid}/bump',
                          data={
                              'bid_increase': second_bid,
                          },
                          headers={'X-Auth-Token': auth_token})
    assert bump_rv.status_code == HTTPStatus.OK

    # Bump again
    third_bid = 3000
    total_bid += third_bid
    invoice3 = new_invoice(1, InvoiceStatus.pending, third_bid)
    charged_auth_token3 = hmac_sha256_digest(constants.LIGHTNING_WEBHOOK_KEY,
                                             invoice3.lid)
    mock_new_invoice.return_value = (True, invoice3)
    bump_rv = client.post(f'/order/{uuid}/bump',
                          data={
                              'bid_increase': third_bid,
                          },
                          headers={'X-Auth-Token': auth_token})
    assert bump_rv.status_code == HTTPStatus.OK

    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_order.unpaid_bid == total_bid

    # pay the first invoice
    rv = client.post(f'/callback/{invoice1.lid}/{charged_auth_token1}')
    assert rv.status_code == HTTPStatus.OK
    # refetch the order and the invoice from the database
    db_invoice = Invoice.query.filter_by(lid=invoice1.lid).first()
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_invoice.status == InvoiceStatus.paid.value
    assert db_invoice.paid_at is not None
    assert db_order.status == OrderStatus.transmitting.value
    assert db_order.bid == first_bid
    assert db_order.unpaid_bid == total_bid - first_bid

    # pay the second invoice
    rv = client.post(f'/callback/{invoice2.lid}/{charged_auth_token2}')
    assert rv.status_code == HTTPStatus.OK
    # refetch the order and the invoice from the database
    db_invoice = Invoice.query.filter_by(lid=invoice2.lid).first()
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_invoice.status == InvoiceStatus.paid.value
    assert db_invoice.paid_at is not None
    assert db_order.status == OrderStatus.transmitting.value
    assert db_order.bid == first_bid + second_bid
    assert db_order.unpaid_bid == total_bid - first_bid - second_bid

    # pay the last invoice
    rv = client.post(f'/callback/{invoice3.lid}/{charged_auth_token3}')
    assert rv.status_code == HTTPStatus.OK
    # refetch the order and the invoice from database
    db_invoice = Invoice.query.filter_by(lid=invoice3.lid).first()
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert db_invoice.status == InvoiceStatus.paid.value
    assert db_invoice.paid_at is not None
    assert db_order.status == OrderStatus.transmitting.value
    assert db_order.bid == total_bid
    assert db_order.unpaid_bid == 0


@patch('orders.new_invoice')
def test_try_to_pay_an_expired_invoice(mock_new_invoice, client):
    n_bytes = 500
    invoice = new_invoice(1, InvoiceStatus.expired,
                          bidding.get_min_bid(n_bytes))
    mock_new_invoice.return_value = (True, invoice)
    post_rv = place_order(client, n_bytes)
    assert post_rv.status_code == HTTPStatus.OK
    uuid_order = post_rv.get_json()['uuid']

    charged_auth_token = hmac_sha256_digest(constants.LIGHTNING_WEBHOOK_KEY,
                                            invoice.lid)
    rv = client.post(f'/callback/{invoice.lid}/{charged_auth_token}')
    assert rv.status_code == HTTPStatus.BAD_REQUEST
    assert_error(rv.get_json(), 'INVOICE_ALREADY_EXPIRED')

    # refetch the order and the invoice from the database
    # expecation is that none of them change their status
    db_invoice = Invoice.query.filter_by(lid=invoice.lid).first()
    db_order = Order.query.filter_by(uuid=uuid_order).first()
    assert db_invoice.status == InvoiceStatus.expired.value
    assert db_order.status == InvoiceStatus.pending.value
    assert db_invoice.paid_at is None
