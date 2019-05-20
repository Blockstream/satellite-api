require "sinatra/activerecord"
require_relative '../constants'
require_relative './orders'

class RxConfirmation < ActiveRecord::Base
  validates :order_id, presence: true
  validates :region_id, presence: true
  
  belongs_to :order
  belongs_to :region  
end
