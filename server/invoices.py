from constants import InvoiceStatus
from error import get_http_error_resp
from flask_restful import Resource
from invoice_helpers import get_and_authenticate_invoice,\
    pay_invoice


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

        if invoice.status == InvoiceStatus.paid.value:
            return get_http_error_resp('ORDER_ALREADY_PAID')

        pay_invoice(invoice)

        return {'message': f'invoice {invoice.lid} paid'}
