require "faraday"

module Sinatra
  module InvoiceHelpers
    
    def fetch_invoice_by_lid
      Invoice.where(lid: params[:lid]).first || 
      error_object("Not found", "Invoice id #{params[:lib]} not found", ERROR::CODES[:INVOICE_ID_NOT_FOUND_ERROR])        
    end
    
    def authorize_invoice!(invoice)
      if invoice.charged_auth_token != params[:charged_auth_token]
        halt 401, error_object("Unauthorized", "Invalid authentication token", ERROR::CODES[:INVALID_AUTH_TOKEN])
      else
        invoice
      end
    end
    
    def get_and_authenticate_invoice
      authorize_invoice!(fetch_invoice_by_lid)
    end
    
    def new_invoice(order, bid)
      bid = Integer(bid)
      # generate Lightning invoice
      charged_response = $lightning_charge.post '/invoice', {
        msatoshi: bid,
        description: LN_INVOICE_DESCRIPTION,
        expiry: LN_INVOICE_EXPIRY, 
        metadata: {uuid: order.uuid, sha256_message_digest: order.message_digest}
      }  
      unless charged_response.status == 201
        halt 400, error_object("Lightning Charge invoice creation error", "received #{response.status} from charged", ERROR::CODES[:LIGHTNING_CHARGE_INVOICE_ERROR])
      end

      lightning_invoice = JSON.parse(charged_response.body)
      invoice = Invoice.new(order: order, amount: bid, lid: lightning_invoice["id"], invoice: charged_response.body, expires_at: Time.now + LN_INVOICE_EXPIRY)

      # register the webhook
      webhook_registration_response = $lightning_charge.post "/invoice/#{invoice.lid}/webhook", {
        url: invoice.callback_url
      }  
      unless webhook_registration_response.status == 201
        halt 400, error_object("Lightning Charge webhook registration error", "received #{response.status} from charged", ERROR::CODES[:LIGHTNING_CHARGE_WEBHOOK_REGISTRATION_ERROR])        
      end
      invoice
    end
    
    def invoice_not_found_error
      halt 404, error_object("Payment problem", "Invoice not found", ERROR::CODES[:INVOICE_NOT_FOUND])
    end
    
    def orphaned_invoice_error
      halt 404, error_object("Payment problem", "Orphaned invoice", ERROR::CODES[:ORPHANED_INVOICE])
    end
    
    def order_already_paid_error
      halt 400, error_object("Payment problem", "Order already paid", ERROR::CODES[:ORDER_ALREADY_PAID])
    end

  end
  helpers InvoiceHelpers
end
