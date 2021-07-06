from http import HTTPStatus
import datetime
import requests

from sqlalchemy import and_, func

from constants import InvoiceStatus
import constants
from database import db
from error import get_http_error_resp
from models import Invoice
from order_helpers import maybe_mark_order_as_expired, maybe_mark_order_as_paid
from utils import hmac_sha256_digest


def new_invoice(order, bid):
    """Generate a lightning invoice

    Args:
      order: The order for which this invoice is being generated.
      bid: Bid amount.
    Returns:
      A pair whose first element is a boolean indicating whether
      the invoice generation was successful or not. If False, then
      the second element is the error key. If True, then the second
      element is the newly generated invoice.
   """
    try:
        bid = int(bid)
        # generate Lightning invoice
        charged_response = requests.post(f"{constants.CHARGE_ROOT}/invoice",
                                         json={
                                             'msatoshi': bid,
                                             'description':
                                             constants.LN_INVOICE_DESCRIPTION,
                                             'expiry':
                                             constants.LN_INVOICE_EXPIRY,
                                             'metadata': {
                                                 'uuid':
                                                 order.uuid,
                                                 'sha256_message_digest':
                                                 order.message_digest
                                             }
                                         },
                                         timeout=(constants.CONNECTION_TIMEOUT,
                                                  constants.RESPONSE_TIMEOUT))
    except requests.exceptions.RequestException:
        return False, get_http_error_resp('LIGHTNING_CHARGE_INVOICE_ERROR')
    except ValueError:
        return False, get_http_error_resp('PARAM_COERCION', 'bid')

    if charged_response.status_code != HTTPStatus.CREATED:
        return False, get_http_error_resp('LIGHTNING_CHARGE_INVOICE_ERROR')

    lightning_invoice = charged_response.json()
    if 'id' not in lightning_invoice:
        return False, get_http_error_resp('LIGHTNING_CHARGE_INVOICE_ERROR')

    invoice = Invoice(order_id=order.id,
                      amount=bid,
                      lid=lightning_invoice['id'],
                      invoice=charged_response.content,
                      status=InvoiceStatus.pending.value,
                      expires_at=datetime.datetime.utcnow() +
                      datetime.timedelta(seconds=constants.LN_INVOICE_EXPIRY))

    try:
        # register the webhook
        charged_auth_token = hmac_sha256_digest(
            constants.LIGHTNING_WEBHOOK_KEY, invoice.lid)
        callback_url = f"{constants.CALLBACK_URI_ROOT}/callback\
            /{invoice.lid}/{charged_auth_token}"

        webhook_registration_response = requests.post(
            f"{constants.CHARGE_ROOT}/invoice/{invoice.lid}/webhook",
            json={'url': callback_url},
            timeout=(constants.CONNECTION_TIMEOUT, constants.RESPONSE_TIMEOUT))

        if webhook_registration_response.status_code != HTTPStatus.CREATED:
            return False, get_http_error_resp(
                'LIGHTNING_CHARGE_WEBHOOK_REGISTRATION_ERROR')

    except requests.exceptions.RequestException:
        return False, get_http_error_resp(
            'LIGHTNING_CHARGE_WEBHOOK_REGISTRATION_ERROR')

    return True, invoice


def get_and_authenticate_invoice(lid, charged_auth_token):
    invoice = Invoice.query.filter_by(lid=lid).first()

    if invoice is None:
        return False, get_http_error_resp('INVOICE_ID_NOT_FOUND_ERROR', lid)

    db_invoice_charged_auth_token = hmac_sha256_digest(
        constants.LIGHTNING_WEBHOOK_KEY, invoice.lid)

    if db_invoice_charged_auth_token != charged_auth_token:
        return False, get_http_error_resp('INVALID_AUTH_TOKEN')

    return True, invoice


def pay_invoice(invoice):
    if invoice.status == InvoiceStatus.paid.value:
        return get_http_error_resp('INVOICE_ALREADY_PAID')
    if invoice.status == InvoiceStatus.expired.value:
        return get_http_error_resp('INVOICE_ALREADY_EXPIRED')

    invoice.status = InvoiceStatus.paid.value
    invoice.paid_at = datetime.datetime.utcnow()
    db.session.commit()
    maybe_mark_order_as_paid(invoice.order_id)
    return None


def get_pending_invoices(order_id):
    return Invoice.query.filter(
        and_(Invoice.order_id == order_id,
             Invoice.status == constants.InvoiceStatus.pending.value)).all()


def expire_invoice(invoice):
    if invoice.status == InvoiceStatus.pending.value:
        invoice.status = constants.InvoiceStatus.expired.value
        db.session.commit()


def expire_unpaid_invoices():
    """Expire unpaid invoices

    Expire any unpaid invoice that has reached its expiration time. The
    corresponding order may be auto-expired as a result.

    Returns:
        Tuple with the list of invoices and the list of orders that got expired
        by this function.

    """
    invoices_to_expire = Invoice.query.filter(
        and_(Invoice.status == constants.InvoiceStatus.pending.value,
             func.datetime(Invoice.expires_at) <
             datetime.datetime.utcnow())).all()
    expired_orders = []
    for invoice in invoices_to_expire:
        expire_invoice(invoice)
        expired_order = maybe_mark_order_as_expired(invoice.order_id)
        if (expired_order is not None):
            expired_orders.append(expired_order)
    return invoices_to_expire, expired_orders
