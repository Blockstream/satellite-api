require 'sinatra'
require "sinatra/activerecord"
require "faraday"
require 'securerandom'
require 'openssl'
require 'time'

require_relative 'constants'
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
    (order = Order.find_by(uuid: params[:uuid], status: [:sent, :transmitting])) || halt(404, {:message => "Not found", :errors => ["Sent order with that id not found"]}.to_json)
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
  param :limit, Integer, default: PAGE_SIZE, max: MAX_QUEUED_ORDERS_REQUEST, message: "can't display more than top #{MAX_QUEUED_ORDERS_REQUEST} orders"
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
    halt 400, {:message => "Invalid date", :errors => ["Couldn't parse date given by before param"]}.to_json
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
    halt 400, {:message => "Invalid date", :errors => ["Couldn't parse date given by before param"]}.to_json
  end
  Order.where(status: :pending).where("created_at < ?", before)
       .select(Order::PUBLIC_FIELDS)
       .order(created_at: :desc)
       .limit(PAGE_SIZE).to_json(:only => Order::PUBLIC_FIELDS)
end

get '/message/:tx_seq_num' do
  (order = Order.find_by(tx_seq_num: params[:tx_seq_num], status: [:sent, :transmitting])) || halt(404, {:message => "Not found", :errors => ["Sent order with that tx sequence number not found"]}.to_json)
  send_file order.message_path, :disposition => 'attachment'
end

# POST /order
#  
# upload a message, along with a bid (in millisatoshis)
# return JSON object with status, uuid, and lightning payment invoice
post '/order' do
  param :bid, Integer, required: true, min: 0, message: "must be a positive integer number of msatoshis"
  param :file, Hash, required: true
  bid = Integer(params[:bid])

  # process the upload
  unless tmpfile = params[:file][:tempfile]
    halt 400, {:message => "Message upload problem", :errors => ["No tempfile received"]}.to_json
  end
  unless name = params[:file][:filename]
    halt 400, {:message => "Message upload problem", :errors => ["Filename missing"]}.to_json
  end

  order = Order.new(uuid: SecureRandom.uuid)
  message_file = File.new(order.message_path, "wb")
  message_size = 0
  sha256 = OpenSSL::Digest::SHA256.new
  while block = tmpfile.read(65536)
    message_size += block.size
    if message_size > MAX_MESSAGE_SIZE
      halt 413, {:message => "Message upload problem", :errors => ["Message size exceeds max size #{MAX_MESSAGE_SIZE}"]}.to_json
    end
    sha256 << block
    message_file.write(block)
  end
  message_file.close()
  if message_size < MIN_MESSAGE_SIZE
    FileUtils.rm(message_file)
    halt 400, {:message => "Message upload problem", :errors => ["Message too small. Minimum message size is #{MIN_MESSAGE_SIZE} byte"]}.to_json
  end

  order.message_size = message_size
  order.message_digest = sha256.to_s

  message_size_with_overhead = message_size + FRAMING_OVERHEAD_PER_FRAGMENT * (message_size / FRAGMENT_SIZE).ceil
  
  if bid.to_f / message_size_with_overhead.to_f < MIN_PER_BYTE_BID
    halt 413, {:message => "Bid too low", :errors => ["Per byte bid cannot be below #{MIN_PER_BYTE_BID} millisatoshis per byte. The minimum bid for this message is #{message_size_with_overhead * MIN_PER_BYTE_BID} millisatoshis." ]}.to_json
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
    halt 400, {:message => "Cannot bump order", :errors => ["Order already #{order.status}"]}.to_json
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
    halt 400, {:message => "Cannot cancel order", :errors => ["Order already #{order.status}"]}.to_json
  end

  {:message => "order cancelled"}.to_json
end

# invoice paid callback from charged
post '/callback/:lid/:charged_auth_token' do
  param :lid, String, required: true
  param :charged_auth_token, String, required: true

  invoice = get_and_authenticate_invoice
  if invoice.nil?
    halt 404, {:message => "Payment problem", :errors => ["Invoice not found"]}.to_json
  end

  unless invoice.order
    halt 404, {:message => "Payment problem", :errors => ["Orphaned invoice"]}.to_json
  end

  if invoice.paid?
    halt 400, {:message => "Payment problem", :errors => ["Order already paid"]}.to_json
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
  redirect "http://#{request.host}:4500/stream?channels=#{params[:channels]}"
end
