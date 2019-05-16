require "sinatra/activerecord"
require_relative '../constants'
require_relative './orders'
require_relative './regions'

class Confirmation < ActiveRecord::Base
  validates :created_at, presence: true
  validates :order_id, presence: true
  validates :region_id, presence: true
  validates :presumed, presence: true
  
  belongs_to :order
  belongs_to :region  
end
