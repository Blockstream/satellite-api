import pytest
import requests
from datetime import datetime, timedelta
from http import HTTPStatus
from requests.exceptions import Timeout
from unittest.mock import MagicMock, Mock, patch

from common import new_invoice
from constants import InvoiceStatus, OrderStatus
from database import db
from error import get_http_error_resp
from models import Order, Invoice
import invoice_helpers
import server

from common import generate_test_order


@pytest.fixture
def client():
    app = server.create_app(from_test=True)
    app.app_context().push()
    with app.test_client() as client:
        yield client
    server.teardown_app(app)


@patch('orders.new_invoice')
def test_expire_pending_invoice(mock_new_invoice, client):
    invoice_id = generate_test_order(
        mock_new_invoice, client,
        invoice_status=InvoiceStatus.pending)['lightning_invoice']['id']

    db_invoice = \
        Invoice.query.filter_by(lid=invoice_id).first()
    invoice_helpers.expire_invoice(db_invoice)

    # refetch and check
    db_invoice = \
        Invoice.query.filter_by(lid=invoice_id).first()
    assert db_invoice.status == InvoiceStatus.expired.value


@patch('orders.new_invoice')
@pytest.mark.parametrize("status",
                         [InvoiceStatus.paid, InvoiceStatus.paid.expired])
def test_expire_non_pending_invoice(mock_new_invoice, client, status):
    invoice_id = generate_test_order(
        mock_new_invoice, client,
        invoice_status=status)['lightning_invoice']['id']

    db_invoice = \
        Invoice.query.filter_by(lid=invoice_id).first()
    invoice_helpers.expire_invoice(db_invoice)

    # refetch and check
    # status should not change
    db_invoice = \
        Invoice.query.filter_by(lid=invoice_id).first()
    assert db_invoice.status == status.value


@patch('orders.new_invoice')
def test_expire_unpaid_invoices(mock_new_invoice, client):
    # prepare test invoices

    # invoice with pending status and a passed expiration date
    to_be_expired = generate_test_order(mock_new_invoice, client, order_id=1)
    to_be_expired_invoice_lid = to_be_expired['lightning_invoice']['id']
    to_be_expired_order_uuid = to_be_expired['uuid']
    to_be_expired_db_invoice = \
        Invoice.query.filter_by(lid=to_be_expired_invoice_lid).first()
    to_be_expired_db_invoice.expires_at = datetime.utcnow() - timedelta(days=1)
    db.session.commit()

    # invoice with paid status
    non_pending_invoice_lid = generate_test_order(
        mock_new_invoice,
        client,
        order_id=2,
        invoice_status=InvoiceStatus.paid)['lightning_invoice']['id']

    # pending invoice whose expiration is not reached yet
    pending_not_yet_expired_invoice_lid = generate_test_order(
        mock_new_invoice, client, order_id=2)['lightning_invoice']['id']

    expired_invoices, expired_orders = invoice_helpers.expire_unpaid_invoices()
    assert len(expired_invoices) == 1
    assert len(expired_orders) == 1
    assert expired_invoices[0].lid == to_be_expired_invoice_lid
    assert expired_orders[0].uuid == to_be_expired_order_uuid

    # refetch and check

    # both the invoice and its corresponding order should be expired
    to_be_expired_db_invoice = \
        Invoice.query.filter_by(lid=to_be_expired_invoice_lid).first()
    assert to_be_expired_db_invoice.status == InvoiceStatus.expired.value
    db_order = Order.query.filter_by(
        id=to_be_expired_db_invoice.order_id).first()
    assert db_order.status == OrderStatus.expired.value

    # neither the invoice nor its corresponding order should change
    non_pending_db_invoice = \
        Invoice.query.filter_by(lid=non_pending_invoice_lid).first()
    assert non_pending_db_invoice.status == InvoiceStatus.paid.value
    db_order = Order.query.filter_by(
        id=non_pending_db_invoice.order_id).first()
    assert db_order.status == OrderStatus.pending.value

    # neither the invoice nor its corresponding order should change
    pending_not_yet_expired_db_invoice = \
        Invoice.query.filter_by(
            lid=pending_not_yet_expired_invoice_lid).first()
    assert pending_not_yet_expired_db_invoice.status ==\
        InvoiceStatus.pending.value
    db_order = Order.query.filter_by(
        id=pending_not_yet_expired_db_invoice.order_id).first()
    assert db_order.status == OrderStatus.pending.value


def test_new_invoice_invalid_bid():
    new_order = Order(uuid='123',
                      unpaid_bid=2000,
                      message_size=10,
                      message_digest='some digest',
                      status=OrderStatus.pending.value)

    assert invoice_helpers.new_invoice(new_order, 'abc') ==\
        (False, get_http_error_resp('PARAM_COERCION', 'bid'))
    assert invoice_helpers.new_invoice(new_order, '') ==\
        (False, get_http_error_resp('PARAM_COERCION', 'bid'))
    assert invoice_helpers.new_invoice(new_order, '1a3') ==\
        (False, get_http_error_resp('PARAM_COERCION', 'bid'))


@patch('invoice_helpers.requests.post')
@pytest.mark.parametrize("http_status", [
    HTTPStatus.OK, HTTPStatus.NOT_FOUND, HTTPStatus.BAD_REQUEST,
    HTTPStatus.UNAUTHORIZED
])
def test_new_invoice_lightning_service_does_not_return_created(
        lightning_service_mock, http_status):
    lightning_service_mock.return_value = Mock()
    lightning_service_mock.return_value.status_code = http_status
    new_order = Order(uuid='123',
                      unpaid_bid=2000,
                      message_size=10,
                      message_digest='some digest',
                      status=OrderStatus.pending.value)
    assert invoice_helpers.new_invoice(new_order, 2000) ==\
        (False, get_http_error_resp('LIGHTNING_CHARGE_INVOICE_ERROR'))


@patch('invoice_helpers.requests.post')
@pytest.mark.parametrize("exception_or_timeout",
                         [requests.exceptions.RequestException, Timeout])
def test_new_invoice_lightning_service_exception_or_timeout(
        lightning_service_mock, exception_or_timeout):
    new_order = Order(uuid='123',
                      unpaid_bid=2000,
                      message_size=10,
                      message_digest='some digest',
                      status=OrderStatus.pending.value)
    lightning_service_mock.side_effect = exception_or_timeout
    assert invoice_helpers.new_invoice(new_order, 2000) ==\
        (False, get_http_error_resp('LIGHTNING_CHARGE_INVOICE_ERROR'))


@patch('invoice_helpers.requests.post')
def test_new_invoice_lightning_service_missing_id_in_response(
        lightning_service_mock):
    SAMPLE_LIGHTNING_INVOICE = str({
        "msatoshi": "50000",
        "description": "BSS Test",
        "rhash": "2d632cd898462dcf",
        "payreq": "lntb500n1psdca8",
        "expires_at": 1625064182,
        "created_at": 1625060582,
        "metadata": {
            "uuid": "470c2b2a-8646-4def-b1bb-71d07706d0e5",
            "sha256_message_digest": "0759807b1e6d5ed5fe0a7d"
        },
        "status": "unpaid"
    })

    lightning_service_mock.return_value.status_code = HTTPStatus.CREATED
    lightning_service_mock.return_value.content =\
        SAMPLE_LIGHTNING_INVOICE.encode()

    new_order = Order(uuid='470c2b2a-8646-4def-b1bb-71d07706d0e5',
                      unpaid_bid=2000,
                      message_size=10,
                      message_digest='0759807b1e6d5ed5fe0a7d',
                      status=OrderStatus.pending.value)
    assert invoice_helpers.new_invoice(new_order, 2000) ==\
        (False, get_http_error_resp('LIGHTNING_CHARGE_INVOICE_ERROR'))


SAMPLE_LIGHTNING_INVOICE = {
    "id": "gWe8iV0jsCVm4tqrUpfit",
    "msatoshi": "50000",
    "description": "BSS Test",
    "rhash": "2d632cd898462dcf",
    "payreq": "lntb500n1psdca8",
    "expires_at": 1625064182,
    "created_at": 1625060582,
    "metadata": {
        "uuid": "470c2b2a-8646-4def-b1bb-71d07706d0e5",
        "sha256_message_digest": "0759807b1e6d5ed5fe0a7d"
    },
    "status": "unpaid"
}


@patch('invoice_helpers.requests.post')
@pytest.mark.parametrize("webhook_http_status", [
    HTTPStatus.OK, HTTPStatus.NOT_FOUND, HTTPStatus.BAD_REQUEST,
    HTTPStatus.UNAUTHORIZED
])
def test_new_invoice_lightning_service_invalid_webhook_response(
        requests_mock, webhook_http_status):
    # There are two requests.post calls in new_invoice function, one for
    # requests to lightning and the other for the webhook. Mock's side_effect
    # is used to mock both of them. Note side_effect is an iterable that
    # produces its next value every time the mocked method is called.
    lightning_response_mock = MagicMock()
    lightning_response_mock.status_code = HTTPStatus.CREATED
    lightning_response_mock.json.return_value = SAMPLE_LIGHTNING_INVOICE
    webhook_response_mock = Mock()
    webhook_response_mock.status_code = webhook_http_status
    requests_mock.side_effect = [
        lightning_response_mock, webhook_response_mock
    ]

    new_order = Order(uuid='470c2b2a-8646-4def-b1bb-71d07706d0e5',
                      unpaid_bid=2000,
                      message_size=10,
                      message_digest='0759807b1e6d5ed5fe0a7d',
                      status=OrderStatus.pending.value)

    assert invoice_helpers.new_invoice(new_order, 2000) ==\
        (False, get_http_error_resp(
            'LIGHTNING_CHARGE_WEBHOOK_REGISTRATION_ERROR'))


@patch('invoice_helpers.requests.post')
@pytest.mark.parametrize("exception_or_timeout",
                         [requests.exceptions.RequestException, Timeout])
def test_new_invoice_webhook_exception_or_timeout(requests_mock,
                                                  exception_or_timeout):
    lightning_response_mock = MagicMock()
    lightning_response_mock.status_code = HTTPStatus.CREATED
    lightning_response_mock.json.return_value = SAMPLE_LIGHTNING_INVOICE
    requests_mock.side_effect = [lightning_response_mock, exception_or_timeout]

    new_order = Order(uuid='470c2b2a-8646-4def-b1bb-71d07706d0e5',
                      unpaid_bid=2000,
                      message_size=10,
                      message_digest='0759807b1e6d5ed5fe0a7d',
                      status=OrderStatus.pending.value)

    assert invoice_helpers.new_invoice(new_order, 2000) ==\
        (False, get_http_error_resp(
            'LIGHTNING_CHARGE_WEBHOOK_REGISTRATION_ERROR'))


@patch('invoice_helpers.requests.post')
def test_new_invoice_successfully(requests_mock):
    lightning_response_mock = MagicMock()
    lightning_response_mock.status_code = HTTPStatus.CREATED
    lightning_response_mock.json.return_value = SAMPLE_LIGHTNING_INVOICE
    webhook_response_mock = Mock()
    webhook_response_mock.status_code = HTTPStatus.CREATED
    requests_mock.side_effect = [
        lightning_response_mock, webhook_response_mock
    ]

    new_order = Order(id=1,
                      uuid='470c2b2a-8646-4def-b1bb-71d07706d0e5',
                      unpaid_bid=2000,
                      message_size=10,
                      message_digest='0759807b1e6d5ed5fe0a7d',
                      status=OrderStatus.pending.value)

    res = invoice_helpers.new_invoice(new_order, 2000)
    assert res[0]
    new_invoice = res[1]
    assert new_invoice.amount == 2000
    assert new_invoice.lid == SAMPLE_LIGHTNING_INVOICE["id"]
    assert new_invoice.status == InvoiceStatus.pending.value


@patch('orders.new_invoice')
def test_get_pending_invoices(mock_new_invoice, client):
    # Create an order and bump it twice so that it ends up with three
    # invoices. Set the second invoice as paid and call
    # get_pending_invoices. The returned list should contain only two invoices.

    # First invoice (pending)
    json_response = generate_test_order(mock_new_invoice, client, bid=2000)
    uuid = json_response['uuid']
    auth_token = json_response['auth_token']
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert len(db_order.invoices) == 1

    # Second invoice (paid)
    mock_new_invoice.return_value = (True,
                                     new_invoice(db_order.id,
                                                 InvoiceStatus.paid, 2000))
    bump_rv = client.post(f'/order/{uuid}/bump',
                          data={
                              'bid_increase': 2000,
                          },
                          headers={'X-Auth-Token': auth_token})
    assert bump_rv.status_code == HTTPStatus.OK
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert len(db_order.invoices) == 2

    # Third invoice (pending)
    mock_new_invoice.return_value = (True,
                                     new_invoice(db_order.id,
                                                 InvoiceStatus.pending, 2000))
    bump_rv = client.post(f'/order/{uuid}/bump',
                          data={
                              'bid_increase': 2000,
                          },
                          headers={'X-Auth-Token': auth_token})
    assert bump_rv.status_code == HTTPStatus.OK
    db_order = Order.query.filter_by(uuid=uuid).first()
    assert len(db_order.invoices) == 3

    # Check the pending invoices
    pending_orders = invoice_helpers.get_pending_invoices(db_order.id)
    assert len(pending_orders) == 2
    assert pending_orders[0].status == InvoiceStatus.pending.value
    assert pending_orders[1].status == InvoiceStatus.pending.value
