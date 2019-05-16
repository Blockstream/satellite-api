require "sinatra/activerecord"
require_relative '../constants'
require_relative './orders'
require_relative './confirmations'

class TxConfirmation < Confirmation
end
