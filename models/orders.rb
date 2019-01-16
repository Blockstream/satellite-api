require 'aasm'
require 'redis'
require 'json'
require_relative '../constants'
require_relative './invoices'
require_relative '../helpers/digest_helpers'

class Order < ActiveRecord::Base
  include AASM

  PUBLIC_FIELDS = [:uuid, :unpaid_bid, :bid, :bid_per_byte, :message_size, :message_digest, :status, :created_at, :started_transmission_at, :ended_transmission_at, :tx_seq_num]

  @@redis = Redis.new(url: REDIS_URI)

  enum status: [:pending, :paid, :transmitting, :sent, :cancelled]

  before_validation :adjust_bids

  validates :bid, presence: true, numericality: { only_integer: true, greater_than_or_equal_to: 0 }
  validates :unpaid_bid, presence: true, numericality: { only_integer: true, greater_than_or_equal_to: 0 }
  validates :message_size, presence: true, numericality: { only_integer: true, greater_than_or_equal_to: MIN_MESSAGE_SIZE }
  validates :message_digest, presence: true
  validates :bid_per_byte, numericality: { greater_than_or_equal_to: 0 }
  validates :status, presence: true
  validates :uuid, presence: true

  has_many :invoices, after_add: :adjust_bids_and_save, after_remove: :adjust_bids_and_save

  aasm :column => :status, :enum => true, :whiny_transitions => false, :no_direct_assignment => true do
    state :pending, initial: true
    state :paid
    state :expired
    state :transmitting, before_enter: Proc.new { self.started_transmission_at = Time.now }
    state :sent, before_enter: Proc.new { self.ended_transmission_at = Time.now }
    state :cancelled, before_enter: Proc.new { self.cancelled_at = Time.now }

    event :pay do
      transitions :from => :pending, :to => :paid, :guard => :paid_enough?
      transitions :from => :paid, :to => :paid
    end

    event :transmit, :after => :notify_transmissions_channel do
      transitions :from => :paid, :to => :transmitting
    end

    event :end_transmission, :after => :notify_transmissions_channel do
      transitions :from => :transmitting, :to => :sent
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
    self.bid_per_byte = (self.bid.to_f / self.message_size.to_f).round(2)
    self.unpaid_bid = unpaid_invoices_total
  end

  def maybe_mark_as_paid
    self.pay! if self.paid_enough?
  end

  def paid_enough?
    self.adjust_bids
    self.bid_per_byte >= MIN_PER_BYTE_BID
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
    File.delete(self.message_path)
  end

end
