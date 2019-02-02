ENV['RACK_ENV'] = 'test'
ENV['CALLBACK_URI_ROOT'] = 'http://localhost:9292'

require 'minitest/autorun'
require 'rack/test'
require 'json'
require_relative '../main'

TEST_FILE = "test.random"
TINY_TEST_FILE = "tiny_test.txt"

unless File.exists?(TEST_FILE) and File.exists?(TINY_TEST_FILE)
  `dd if=/dev/random of=#{TEST_FILE} bs=1k count=#{MAX_MESSAGE_SIZE / KILO_BYTE}`
  `echo "abcdefghijklmnopqrstuvwxyz" > #{TINY_TEST_FILE}`
end

DEFAULT_BID = File.stat(TEST_FILE).size * (MIN_PER_BYTE_BID + 1)

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
  
  def write_response
    File.open('response.html', 'w') { |file| file.write(last_response.body) }
  end
  
  def order_is_queued(uuid)
    get "/orders/queued?limit=#{MAX_PAGE_SIZE}"
    assert last_response.ok?
    r = JSON.parse(last_response.body)
    uuids = r.map {|o| o['uuid']}
    uuids.include?(uuid)
  end

  def test_get_orders_queued
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
  
  def test_bid_too_low
    post '/order', params={"bid" => 1, "file" => Rack::Test::UploadedFile.new(TEST_FILE, "image/png")}
    refute last_response.ok?
    r = JSON.parse(last_response.body)
    assert_equal r['message'], 'Bid too low'
    refute_nil r['errors']
  end
  
  def test_no_file_uploaded
    post '/order', params={"bid" => DEFAULT_BID}
    refute last_response.ok?
  end

  def test_uploaded_file_too_large
    skip "test later"
  end

  def test_uploaded_file_too_small
    post '/order', params={"bid" => DEFAULT_BID, "file" => Rack::Test::UploadedFile.new(TINY_TEST_FILE, "text/plain")}
    refute last_response.ok?
    r = JSON.parse(last_response.body)
    assert_match "too small", r["errors"][0]
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

    pay_invoice(@order.invoices.last)
    @order.reload
    @order.transmit!
    get "/order/#{@order.uuid}/sent_message"
    assert last_response.ok?
    
    @order.end_transmission!
    get "/order/#{@order.uuid}/sent_message"
    assert last_response.ok?
    
  end

end
