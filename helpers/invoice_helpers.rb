require "faraday"

module Sinatra
  module InvoiceHelpers
    
    def fetch_invoice_by_lid
      Invoice.where(lid: params[:lid]).first || halt(404, {:message => "Not found", :errors => ["Invalid invoice id"]}.to_json)
    end
    
    def authorize_invoice!(invoice)
      if invoice.charged_auth_token != params[:charged_auth_token]
        halt 401, {:message => "Unauthorized", :errors => ["Invalid authentication token"]}.to_json
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
        halt 400, {:message => "Lightning Charge invoice creation error", :errors => ["received #{response.status} from charged"]}.to_json
      end

      lightning_invoice = JSON.parse(charged_response.body)
      invoice = Invoice.new(order: order, amount: bid, lid: lightning_invoice["id"], invoice: charged_response.body, expires_at: Time.now + LN_INVOICE_EXPIRY)

      # register the webhook
      webhook_registration_response = $lightning_charge.post "/invoice/#{invoice.lid}/webhook", {
        url: invoice.callback_url
      }  
      unless webhook_registration_response.status == 201
        halt 400, {:message => "Lightning Charge webhook registration error", :errors => ["received #{response.status} from charged"]}.to_json
      end
      invoice
    end

  end
  helpers InvoiceHelpers
end
