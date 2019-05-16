require "sinatra/activerecord"
require_relative '../constants'
require_relative './orders'
require_relative './regions'

class Region < ActiveRecord::Base
  validates :created_at, presence: true
  validates :number, presence: true
  has_many :tx_confirmations
  has_many :rx_confirmations
end
