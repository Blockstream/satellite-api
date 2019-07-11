require 'active_record'

require 'logger'
logger = Logger.new(STDOUT)
logger.level = Logger::INFO

require_relative '../constants'
require_relative '../models/init'

# complete any old transmissions that could be stuck (e.g. by early termination of the transmitter daemon)
Order.transmitting.each do |order|
  logger.info "completing stuck transmission #{order.uuid}"
  order.end_transmission!
end

CLEANUP_DUTY_CYCLE = 5 * 60 # five minutes
last_cleanup_at = Time.now - CLEANUP_DUTY_CYCLE

# loop forever dequing the highest-priced paid order and piping it to the GNU radio FIFO
loop do
  sendable_order = nil
  while sendable_order.nil? do
    if Time.now > last_cleanup_at + CLEANUP_DUTY_CYCLE
      # expire any unpaid invoices that have reached their expiration time (orders may be auto-expired as a result)
      Invoice.where(status: :pending).where("expires_at < ?", Time.now).each { |i| i.expire! }

      # expire old pending orders
      Order.where(status: :pending).where("created_at < ?", Time.now - EXPIRE_PENDING_ORDERS_AFTER).each { |o| o.expire! }
    
      # delete message files for messages sent long ago
      Order.where("ended_transmission_at < ?", Time.now - MESSAGE_FILE_RETENTION_TIME).each { |o| o.delete_message_file }
      
      last_cleanup_at = Time.now
    end
    
    sleep 1
    
    # look for an elligble order to transmit and, if one is found, begin transmitting it
    sendable_order = Order.where(status: :paid).order(bid_per_byte: :desc).first
    if sendable_order
      logger.info "transmission start #{sendable_order.uuid}"
      sendable_order.transmit!
    end
    
  end  
  
  if TRANSMIT_RATE
    transmit_time = Float(sendable_order.message_size) / TRANSMIT_RATE
    logger.info "sleeping for #{transmit_time} while #{sendable_order.uuid} transmits"
    sleep transmit_time
  end
  
  logger.info "transmission end #{sendable_order.uuid}"
  sendable_order.end_transmission!
end
