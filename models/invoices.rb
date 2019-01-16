require 'aasm'
require "sinatra/activerecord"
require_relative '../constants'
require_relative './orders'
require_relative '../helpers/digest_helpers'

class Invoice < ActiveRecord::Base
  include AASM

  enum status: [:pending, :paid, :expired]
  validates :lid, presence: true
  validates :invoice, presence: true
  validates :expires_at, presence: true

  belongs_to :order
  
  aasm :column => :status, :enum => true, :whiny_transitions => false, :no_direct_assignment => true do
    state :pending, initial: true
    state :expired, after_enter: Proc.new { self.order.expire_if_pending_and_no_pending_invoices }
    state :paid, before_enter: Proc.new { self.paid_at = Time.now }, after_enter: Proc.new { self.order.maybe_mark_as_paid }

    event :pay do
      transitions :from => :pending, :to => :paid
    end
    
    event :expire do
      transitions :from => :pending, :to => :expired
    end
  end
  
  LIGHTNING_WEBHOOK_KEY = hash_hmac('sha256', 'charged-token', CHARGE_API_TOKEN)
  def charged_auth_token
    hash_hmac('sha256', LIGHTNING_WEBHOOK_KEY, self.lid)
  end
  
  def callback_url
    "#{CALLBACK_URI_ROOT}/callback/#{self.lid}/#{self.charged_auth_token}"
  end
  
end
