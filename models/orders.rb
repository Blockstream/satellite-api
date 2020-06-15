require 'aasm'
require 'redis'
require 'json'
require_relative '../constants'
require_relative './invoices'
require_relative './tx_confirmations'
require_relative './rx_confirmations'
require_relative '../helpers/digest_helpers'

class Order < ActiveRecord::Base
  include AASM

  PUBLIC_FIELDS = [:uuid, :unpaid_bid, :bid, :bid_per_byte, :message_size, :message_digest, :status, :created_at, :started_transmission_at, :ended_transmission_at, :tx_seq_num]

  @@redis = Redis.new(url: REDIS_URI)

  enum status: [:pending, :paid, :transmitting, :sent, :received, :cancelled, :expired]

  before_validation :adjust_bids

  validates :bid, presence: true, numericality: { only_integer: true, greater_than_or_equal_to: 0 }
  validates :unpaid_bid, presence: true, numericality: { only_integer: true, greater_than_or_equal_to: 0 }
  validates :message_size, presence: true, numericality: { only_integer: true, greater_than_or_equal_to: MIN_MESSAGE_SIZE }
  validates :message_digest, presence: true
  validates :bid_per_byte, numericality: { greater_than_or_equal_to: 0 }
  validates :status, presence: true
  validates :uuid, presence: true

  has_many :invoices, after_add: :adjust_bids_and_save, after_remove: :adjust_bids_and_save
  has_many :tx_confirmations, after_add: :maybe_mark_as_received
  has_many :tx_regions, through: :tx_confirmations, source: :region
  has_many :rx_confirmations, after_add: :maybe_mark_as_received
  has_many :rx_regions, through: :rx_confirmations, source: :region

  aasm :column => :status, :enum => true, :whiny_transitions => false, :no_direct_assignment => true do
    state :pending, initial: true
    state :paid
    state :expired
    state :transmitting, before_enter: Proc.new { self.started_transmission_at = Time.now }
    state :sent, before_enter: Proc.new { self.ended_transmission_at = Time.now }
    state :received
    state :cancelled, before_enter: Proc.new { self.cancelled_at = Time.now }

    event :pay do
      transitions :from => :pending, :to => :paid, :guard => :paid_enough?
      transitions :from => :paid, :to => :paid
    end

    event :transmit, :before => :assign_tx_seq_num, :after => :notify_transmissions_channel do
      transitions :from => :paid, :to => :transmitting
    end

    event :end_transmission, :after => :notify_transmissions_channel do
      transitions :from => :transmitting, :to => :sent
    end
    
    event :receive, :after => :synthesize_presumed_rx_confirmations do
      transitions :from => :sent, :to => :received
    end

    event :cancel, :after => :delete_message_file do
      transitions :from => [:pending, :paid], :to => :cancelled
    end

    event :bump do
      transitions :from => :pending, :to => :pending
      transitions :from => :paid, :to => :paid
    end

    event :expire, :after => :delete_message_file do
      transitions :from => :pending, :to => :expired
    end
  end

  def adjust_bids_and_save(invoice)
    self.adjust_bids
    self.save
  end

  def adjust_bids
    self.bid = paid_invoices_total
    self.bid_per_byte = (self.bid.to_f / self.message_size_with_overhead).round(2)
    self.unpaid_bid = unpaid_invoices_total
  end

  def maybe_mark_as_paid
    self.pay! if self.paid_enough?
  end
  
  def maybe_mark_as_received(confirmation)
    self.receive! if self.received_criteria_met?
  end
  
  def received_criteria_met?
    self.tx_regions.exists?(Region::REGIONS[:north_america].id) &&
    self.tx_regions.exists?(Region::REGIONS[:south_america].id) &&
    self.tx_regions.exists?(Region::REGIONS[:africa].id) &&
    self.tx_regions.exists?(Region::REGIONS[:europe].id) &&
    self.tx_regions.exists?(Region::REGIONS[:asia_c].id) &&
    self.tx_regions.exists?(Region::REGIONS[:asia_ku].id) &&
    self.rx_regions.exists?(Region::REGIONS[:north_america].id) &&
    self.rx_regions.exists?(Region::REGIONS[:south_america].id) &&
    self.rx_regions.exists?(Region::REGIONS[:asia_c].id) &&
    self.rx_regions.exists?(Region::REGIONS[:asia_ku].id)
  end
  
  def synthesize_presumed_rx_confirmations
    [:africa, :europe].each do |r|
      RxConfirmation.create(order: self, region: Region::REGIONS[r], presumed: true)
    end
  end

  def paid_enough?
    self.adjust_bids
    self.bid_per_byte >= MIN_PER_BYTE_BID
  end
  
  def message_size_with_overhead
    n_frags  = (self.message_size.to_f / MAX_BLOCKSAT_PAYLOAD).ceil
    overhead = n_frags * L2_OVERHEAD
    self.message_size.to_f + overhead
  end

  def paid_invoices_total
    self.invoices.where(status: :paid).pluck(:amount).reduce(:+) || 0
  end

  def unpaid_invoices_total
    self.pending_invoices.pluck(:amount).reduce(:+) || 0
  end

  def pending_invoices
    self.invoices.where(status: :pending)
  end

  def expire_if_pending_and_no_pending_invoices
    self.expire! if self.pending? and self.pending_invoices.empty?
  end

  def notify_transmissions_channel
    @@redis.publish 'transmissions', self.to_json(:only => Order::PUBLIC_FIELDS)
  end

  def message_path
    File.join(MESSAGE_STORE_PATH, self.uuid)
  end

  # have all invoices been paid?
  def invoices_all_paid?
    self.invoices.pluck(:paid_at).map {|i| not i.nil?}.reduce(:&)
  end

  USER_AUTH_KEY = hash_hmac('sha256', 'user-token', CHARGE_API_TOKEN)
  def user_auth_token
    hash_hmac('sha256', USER_AUTH_KEY, self.uuid)
  end

  def as_sanitized_json
    self.to_json(:only => Order::PUBLIC_FIELDS)
  end

  def delete_message_file
    File.delete(self.message_path) if File.file?(self.message_path)
  end
  
  # NB: no mutex is needed around max_tx_seq_num because it is assumed that there is only one transmitter
  def assign_tx_seq_num
    self.update(tx_seq_num: Order.max_tx_seq_num + 1)  
  end

  def Order.max_tx_seq_num
    Order.maximum(:tx_seq_num) || 0
  end

  # TODO return queue length, top bid, time to front, and other stats.
  def self.stats
    
  end
end
