from constants import OrderStatus
from error import get_http_error_resp
from flask_restful import Resource
from invoice_helpers import get_and_authenticate_invoice, \
    pay_invoice
from models import Order
import transmitter


class InvoiceResource(Resource):
    # invoice paid callback from charged
    def post(self, lid, charged_auth_token):
        success, invoice_or_error = get_and_authenticate_invoice(
            lid, charged_auth_token)
        if not success:
            return invoice_or_error
        invoice = invoice_or_error
        if not invoice.order_id:
            return get_http_error_resp('ORPHANED_INVOICE')

        error_msg = pay_invoice(invoice)
        if error_msg:
            return error_msg

        order = Order.query.filter_by(id=invoice.order_id).first()
        if order.status == OrderStatus.paid.value:
            transmitter.tx_start(order.channel)

        return {'message': f'invoice {invoice.lid} paid'}
