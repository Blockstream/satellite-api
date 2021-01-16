ENV['RACK_ENV'] = 'test'
ENV['CALLBACK_URI_ROOT'] = 'http://localhost:9292'

require 'minitest/autorun'
require 'rack/test'
require 'json'
require_relative '../main'

TEST_FILE = "test.random"
TINY_TEST_FILE = "zero_length_test_file.txt"

unless File.exists?(TEST_FILE) and File.exists?(TINY_TEST_FILE)
  `dd if=/dev/urandom of=#{TEST_FILE} bs=1k count=#{MAX_MESSAGE_SIZE / KILO_BYTE}`
  `touch #{TINY_TEST_FILE}`
end

DEFAULT_OVERHEAD = (File.stat(TEST_FILE).size / MAX_BLOCKSAT_PAYLOAD).ceil * L2_OVERHEAD
DEFAULT_BID = (File.stat(TEST_FILE).size + DEFAULT_OVERHEAD) * (MIN_PER_BYTE_BID + 1)

class MainAppTest < Minitest::Test
  include Rack::Test::Methods

  def app
    Sinatra::Application
  end

  def place_order(bid = DEFAULT_BID)
    post '/order', params={"bid" => bid, "file" => Rack::Test::UploadedFile.new(TEST_FILE, "image/png")}
    r = JSON.parse(last_response.body)
    Order.find_by_uuid(r['uuid'])
  end

  def bump_order(order, amount)
    header 'X-Auth-Token', order.user_auth_token
    post "/order/#{order.uuid}/bump", params={"bid_increase" => amount}
    r = JSON.parse(last_response.body)
    r['lightning_invoice']
  end

  def setup
    @order = place_order
  end

  def pay_invoice(invoice)
    post "/callback/#{invoice.lid}/#{invoice.charged_auth_token}"
    assert last_response.ok?
  end
  
  def create_pay_and_transmit_order
    @order = place_order
    pay_invoice(@order.invoices.last)
    @order.reload
    @order.transmit!
    @order.end_transmission!
    @order.reload
    assert @order.sent?
    @order
  end

  def write_response
    File.open('response.html', 'w') { |file| file.write(last_response.body) }
  end

  def last_response_error_code
    r = JSON.parse(last_response.body)
    Integer(r["errors"].first["code"])
  end

  def order_is_queued(uuid)
    get "/orders/queued?limit=#{MAX_PAGE_SIZE}"
    assert last_response.ok?
    r = JSON.parse(last_response.body)
    uuids = r.map {|o| o['uuid']}
    uuids.include?(uuid)
  end

  def test_get_orders_queued
    get "/orders/queued?limit=#{MAX_PAGE_SIZE + 1}"
    refute last_response.ok?
    r = JSON.parse(last_response.body)
    assert_equal ERROR::CODES[:LIMIT_TOO_LARGE], last_response_error_code

    get "/orders/queued?limit=#{MAX_PAGE_SIZE}"
    assert last_response.ok?
    r = JSON.parse(last_response.body)
    queued_before = r.count
    @order = place_order
    pay_invoice(@order.invoices.last)
    assert order_is_queued(@order.uuid)
    get "/orders/queued?limit=#{MAX_PAGE_SIZE}"
    assert last_response.ok?
    r = JSON.parse(last_response.body)
    queued_after = r.count
    assert_equal queued_after, queued_before + 1
  end

  def test_get_orders_sent
    get '/orders/sent'
    assert last_response.ok?
  end

  def test_get_order
    place_order
    assert last_response.ok?
    r = JSON.parse(last_response.body)
    header 'X-Auth-Token', r['auth_token']
    get %Q(/order/#{r['uuid']})
    assert last_response.ok?
  end

  def test_order_creation
    place_order
    assert last_response.ok?
    r = JSON.parse(last_response.body)
    refute_nil r['auth_token']
    refute_nil r['uuid']
    refute_nil r['lightning_invoice']
  end

  def message_as_param_test(message)
    post '/order', params={"bid" => DEFAULT_BID, "message" => message}
    assert last_response.ok?
    r = JSON.parse(last_response.body)
    refute_nil r['auth_token']
    refute_nil r['uuid']
    refute_nil r['lightning_invoice']
  end

  def test_message_as_param
    message_as_param_test('!' * 10)
    message_as_param_test('!' * 1024)
    post '/order', params={"bid" => DEFAULT_BID, "message" => '!' * 1025}
    refute last_response.ok?
  end

  def test_negative_bid
    post '/order', params={"bid" => -1, "file" => Rack::Test::UploadedFile.new(TEST_FILE, "image/png")}
    refute last_response.ok?
    assert_equal ERROR::CODES[:BID_TOO_SMALL], last_response_error_code
  end

  def test_bid_below_min_bid
    post '/order', params={"bid" => (4 + L2_OVERHEAD), "message" => "test"}
    refute last_response.ok?
    assert_equal ERROR::CODES[:BID_TOO_SMALL], last_response_error_code
    post '/order', params={"bid" => (MIN_BID - 1), "message" => "test"}
    refute last_response.ok?
    assert_equal ERROR::CODES[:BID_TOO_SMALL], last_response_error_code
    post '/order', params={"bid" => (MIN_BID), "message" => "test"}
    assert last_response.ok?
  end

  def test_bid_too_low
    post '/order', params={"bid" => 1, "file" => Rack::Test::UploadedFile.new(TEST_FILE, "image/png")}
    refute last_response.ok?
    assert_equal ERROR::CODES[:BID_TOO_SMALL], last_response_error_code
  end

  def test_order_without_message
    post '/order', params={"bid" => DEFAULT_BID}
    refute last_response.ok?
    assert_equal ERROR::CODES[:MESSAGE_MISSING], last_response_error_code
  end

  def test_uploaded_file_too_large
    skip "test later"
  end

  def test_uploaded_file_too_small
    post '/order', params={"bid" => DEFAULT_BID, "file" => Rack::Test::UploadedFile.new(TINY_TEST_FILE, "text/plain")}
    refute last_response.ok?
    assert_equal ERROR::CODES[:MESSAGE_FILE_TOO_SMALL], last_response_error_code
  end

  def test_bid_increase_missing_error
    header 'X-Auth-Token', @order.user_auth_token
    post "/order/#{@order.uuid}/bump"
    refute last_response.ok?
    assert_equal ERROR::CODES[:BID_INCREASE_MISSING], last_response_error_code
  end

  def test_negative_bid_increase_error
    bump_order(@order, -1)
    refute last_response.ok?
    assert_equal ERROR::CODES[:BID_INCREASE_TOO_SMALL], last_response_error_code
  end

  def test_invalid_auth_token_error
    header 'X-Auth-Token', "not an auth token"
    post "/order/#{@order.uuid}/bump", params={"bid_increase" => DEFAULT_BID / 2}
    refute last_response.ok?
    assert_equal ERROR::CODES[:INVALID_AUTH_TOKEN], last_response_error_code
  end

  def test_bump
    # place an order
    @order = place_order
    refute order_is_queued(@order.uuid)
    @order.reload
    assert_equal 0, @order.bid
    assert_equal DEFAULT_BID, @order.unpaid_bid

    first_invoice = @order.invoices.first
    pay_invoice(first_invoice)
    assert order_is_queued(@order.uuid)
    @order.reload
    assert_equal DEFAULT_BID, @order.bid
    assert @order.bid_per_byte > 0
    assert_equal 0, @order.unpaid_bid
    bid_pre = @order.bid
    bid_per_byte_pre = @order.bid_per_byte
    unpaid_bid_pre = @order.unpaid_bid

    # bump it
    bump_order(@order, DEFAULT_BID / 2)
    assert last_response.ok?
    @order.reload
    assert_equal bid_pre, @order.bid
    assert_equal bid_per_byte_pre, @order.bid_per_byte
    assert_equal DEFAULT_BID / 2, @order.unpaid_bid
    bid_pre = @order.bid
    bid_per_byte_pre = @order.bid_per_byte

    r = JSON.parse(last_response.body)
    refute_nil r['auth_token']
    refute_nil r['uuid']
    refute_nil r['lightning_invoice']
    lid = r['lightning_invoice']['id']
    assert order_is_queued(@order.uuid)

    # pay the bump
    second_invoice = Invoice.find_by_lid(lid)
    pay_invoice(second_invoice)
    @order.reload
    assert_equal DEFAULT_BID + DEFAULT_BID / 2, @order.bid
    assert @order.bid_per_byte > bid_per_byte_pre
    assert_equal 0, @order.unpaid_bid
  end

  def test_paying_small_invoices_doesnt_result_in_paid_order
    place_order
    refute @order.paid?
    first_invoice = @order.invoices.first
    bump_order(@order, 123)
    refute @order.paid?
    second_invoice = @order.invoices.where(amount: 123).first
    pay_invoice(second_invoice)
    @order.reload
    refute @order.paid?
    pay_invoice(first_invoice)
    @order.reload
    assert @order.paid?
  end

  def test_that_bumping_down_fails
    bump_order(@order, -1)
    refute last_response.ok?
    assert_equal ERROR::CODES[:BID_INCREASE_TOO_SMALL], last_response_error_code
  end

  def test_order_deletion
    @order = place_order
    assert File.file?(@order.message_path)
    header 'X-Auth-Token', @order.user_auth_token
    cancelled_before = Order.where(status: :cancelled).count
    delete "/order/#{@order.uuid}"
    refute File.file?(@order.message_path)
    cancelled_after = Order.where(status: :cancelled).count
    assert last_response.ok?
    assert_equal cancelled_after, cancelled_before + 1
    delete "/order/#{@order.uuid}"
    refute last_response.ok?
  end

  def test_get_sent_message
    @order = place_order
    get "/order/#{@order.uuid}/sent_message"
    refute last_response.ok?
    assert_equal ERROR::CODES[:ORDER_NOT_FOUND], last_response_error_code

    pay_invoice(@order.invoices.last)
    @order.reload
    @order.transmit!
    get "/order/#{@order.uuid}/sent_message"
    assert last_response.ok?

    @order.end_transmission!
    get "/order/#{@order.uuid}/sent_message"
    assert last_response.ok?
  end

  def test_channel_subscription
    get "/subscribe/not_a_channel"
    refute last_response.ok?
    assert_equal ERROR::CODES[:CHANNELS_EQUALITY], last_response_error_code
  end
  
  def test_tx_confirmations
    @order = create_pay_and_transmit_order
    assert_equal 0, @order.tx_confirmations.count

    post "/order/tx/#{@order.tx_seq_num}", params={"regions" => [0].to_json}
    assert last_response.ok?
    @order.reload
    assert_equal 1, @order.tx_confirmations.count
    assert_equal 1, @order.tx_regions.count
    assert @order.sent?

    # try an invalid region number
    post "/order/tx/#{@order.tx_seq_num}", params={"regions" => [9999999].to_json}
    refute last_response.ok?
    @order.reload
    assert_equal 1, @order.tx_confirmations.count
    assert_equal 1, @order.tx_regions.count
    assert @order.sent?
    
    post "/order/tx/#{@order.tx_seq_num}", params={"regions" => [1, 2, 3, 4].to_json}
    assert last_response.ok?
    @order.reload
    assert_equal 5, @order.tx_confirmations.count
    assert_equal 5, @order.tx_regions.count
    assert @order.sent?
  end

  def test_rx_confirmations
    @order = create_pay_and_transmit_order
    assert_equal 0, @order.tx_confirmations.count
    assert_equal 0, @order.rx_confirmations.count

    post "/order/rx/#{@order.tx_seq_num}", params={"region" => 0}
    assert last_response.ok?
    @order.reload
    assert_equal 1, @order.rx_confirmations.count
    assert_equal 1, @order.rx_regions.count
    assert @order.sent?

    post "/order/tx/#{@order.tx_seq_num}", params={"regions" => [0, 1, 2, 3, 4, 5].to_json}
    assert last_response.ok?
    @order.reload
    assert_equal 6, @order.tx_confirmations.count
    assert_equal 6, @order.tx_regions.count
    assert @order.sent?

    post "/order/rx/#{@order.tx_seq_num}", params={"region" => 1}
    assert last_response.ok?
    @order.reload
    assert_equal 2, @order.rx_confirmations.count
    assert_equal 2, @order.rx_regions.count

    post "/order/rx/#{@order.tx_seq_num}", params={"region" => 4}
    assert last_response.ok?
    @order.reload
    assert_equal 3, @order.rx_confirmations.count
    assert_equal 3, @order.rx_regions.count

    # Once all required regions are confirmed (0, 1, 4, and 5), the two other
    # regions (2 and 3) are expected to have inferred rx confirmations
    post "/order/rx/#{@order.tx_seq_num}", params={"region" => 5}
    assert last_response.ok?
    @order.reload
    assert_equal 6, @order.rx_confirmations.count
    assert_equal 6, @order.rx_regions.count
    assert @order.received?
  end

end
