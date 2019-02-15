require 'sinatra'
require "sinatra/activerecord"
require 'sinatra/param'
require "faraday"
require 'securerandom'
require 'openssl'
require 'time'
require 'tempfile'

require_relative 'constants'
require_relative 'error_handlers'
require_relative './models/init'
require_relative 'helpers/init'

configure do
  set :raise_errors, false
  set :show_exceptions, :after_handler

  $lightning_charge = Faraday.new(:url => CHARGE_ROOT)  
end

before do
  content_type :json
end

configure :test, :development do
  get '/order/:uuid/sent_message' do
    (order = Order.find_by(uuid: params[:uuid], status: [:sent, :transmitting])) || uuid_not_found_error
    send_file order.message_path, :disposition => 'attachment'
  end
end

# GET /info
#
# returns:
#   information about the c-lightning node where satellite API payments are terminated
#
get '/info' do
  # call lightning-charge info, which invokes lightning-cli getinfo
  response = $lightning_charge.get '/info'
  response.body
end

# GET /orders/queued
# params: 
#   limit - return top limit orders (optional)
# returns:
#   array of JSON orders sorted by bid-per-byte descending
get '/orders/queued' do
  param :limit, Integer, default: PAGE_SIZE, max: MAX_PAGE_SIZE, message: "can't display more than top #{MAX_PAGE_SIZE} orders"
  Order.where(status: [:paid, :transmitting])
       .select(Order::PUBLIC_FIELDS)
       .order(bid_per_byte: :desc)
       .limit(params[:limit]).to_json(:only => Order::PUBLIC_FIELDS)
end

# GET /orders/sent
# params: 
#   before - return the previous PAGE_SIZE orders sent before the given time (time should be sent as in ISO 8601 format and defaults to now)
# returns:
#   array of JSON orders sorted in reverse chronological order
get '/orders/sent' do
  param :before, String, required: false, default: lambda { Time.now.utc.iso8601 }
  begin
    before = DateTime.iso8601(params[:before])
  rescue
    invalid_date_error
  end
  Order.where(status: :sent).where("created_at < ?", before)
       .select(Order::PUBLIC_FIELDS)
       .order(ended_transmission_at: :desc)
       .limit(PAGE_SIZE).to_json(:only => Order::PUBLIC_FIELDS)
end

# GET /orders/pending
# params: 
#   before - return the previous PAGE_SIZE orders sent before the given time (time should be sent as in ISO 8601 format and defaults to now)
# returns:
#   array of JSON orders sorted in reverse chronological order
get '/orders/pending' do
  param :before, String, required: false, default: lambda { Time.now.utc.iso8601 }
  begin
    before = DateTime.iso8601(params[:before])
  rescue
    invalid_date_error
  end
  Order.where(status: :pending).where("created_at < ?", before)
       .select(Order::PUBLIC_FIELDS)
       .order(created_at: :desc)
       .limit(PAGE_SIZE).to_json(:only => Order::PUBLIC_FIELDS)
end

get '/message/:tx_seq_num' do
  (order = Order.find_by(tx_seq_num: params[:tx_seq_num], status: [:sent, :transmitting])) || sequence_number_not_found_error
  send_file order.message_path, :disposition => 'attachment'
end

# POST /order
#  
# upload a message, along with a bid (in millisatoshis)
# return JSON object with status, uuid, and lightning payment invoice
post '/order' do
  param :bid, Integer, required: true, min: 0, message: "must be a positive integer number of msatoshis"
  param :file, Hash, required: false
  param :message, String, required: false, max_length: 1024

  bid = Integer(params[:bid])

  if params[:message]
    tmpfile = Tempfile.new('message_param')
    tmpfile.write(params[:message])
    tmpfile.close
  elsif params[:file]
    unless tmpfile = params[:file][:tempfile]
      message_file_missing_error
    end
  else
    message_missing_error
  end

  order = Order.new(uuid: SecureRandom.uuid)
  message_file = File.new(order.message_path, "wb")
  message_size = 0
  sha256 = OpenSSL::Digest::SHA256.new
  tmpfile.open
  while block = tmpfile.read(65536)
    message_size += block.size
    if message_size > MAX_MESSAGE_SIZE
      message_file_too_large_error
    end
    sha256 << block
    message_file.write(block)
  end
  message_file.close()
  if message_size < MIN_MESSAGE_SIZE
    FileUtils.rm(message_file)
    message_file_too_small_error
  end

  order.message_size = message_size
  order.message_digest = sha256.to_s

  message_size_with_overhead = message_size + FRAMING_OVERHEAD_PER_FRAGMENT * (message_size / FRAGMENT_SIZE).ceil
  
  if bid.to_f / message_size_with_overhead.to_f < MIN_PER_BYTE_BID
    bid_too_small_error(message_size_with_overhead * MIN_PER_BYTE_BID)
  end

  invoice = new_invoice(order, bid)
  order.invoices << invoice
  order.save
  
  {:auth_token => order.user_auth_token, :uuid => order.uuid, :lightning_invoice => JSON.parse(invoice.invoice)}.to_json
end

post '/order/:uuid/bump' do
  param :uuid, String, required: true
  param :bid_increase, Integer, required: true, min: 0, message: "must be a positive integer number of msatoshis"
  param :auth_token, String, required: true, default: lambda { env['HTTP_X_AUTH_TOKEN'] },
        message: "auth_token must be provided either in the DELETE body or in an X-Auth-Token header"
  bid_increase = Integer(params[:bid_increase])
  
  order = get_and_authenticate_order
  unless order.bump
    order_bump_error
  end
  
  invoice = new_invoice(order, bid_increase)
  order.invoices << invoice
  order.save
  
  {:auth_token => order.user_auth_token, :uuid => order.uuid, :lightning_invoice => JSON.parse(invoice.invoice)}.to_json
end

get '/order/:uuid' do
  param :uuid, String, required: true
  param :auth_token, String, required: true, default: lambda { env['HTTP_X_AUTH_TOKEN'] },
        message: "auth_token must be provided either in the DELETE body or in an X-Auth-Token header"
  get_and_authenticate_order.as_sanitized_json
end

delete '/order/:uuid' do
  param :uuid, String, required: true
  param :auth_token, String, required: true, default: lambda { env['HTTP_X_AUTH_TOKEN'] },
        message: "auth_token must be provided either in the DELETE body or in an X-Auth-Token header"

  order = get_and_authenticate_order
  unless order.cancel!
    order_cancellation_error
  end

  {:message => "order cancelled"}.to_json
end

# invoice paid callback from charged
post '/callback/:lid/:charged_auth_token' do
  param :lid, String, required: true
  param :charged_auth_token, String, required: true

  invoice = get_and_authenticate_invoice
  if invoice.nil?
    invoice_not_found_error
  end

  unless invoice.order
    orphaned_invoice_error
  end

  if invoice.paid?
    order_already_paid_error
  end
  
  invoice.pay!
  
  {:message => "invoice #{invoice.lid} paid"}.to_json
end

# subscribe to one or more SSE channels
# params: 
#   channels - comma-separated list of channels to subscribe to
# returns:
#   SSE event stream
# available channels:
#   transmissions - an event is pushed to this channel when each message transmission begins and ends
get '/subscribe/:channels' do
  param :channels, String, is: 'transmissions'
  redirect "http://#{request.host}:4500/stream?channels=#{params[:channels]}"
end
