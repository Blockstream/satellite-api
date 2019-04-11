module Sinatra
  module OrderHelpers
    
    def fetch_order_by_uuid
      Order.where(uuid: params[:uuid]).first || uuid_not_found_error
    end
    
    def authorize_order!(order)
      if order.user_auth_token != params[:auth_token]
        halt 401, error_object("Unauthorized", "Invalid authentication token", ERROR::CODES[:INVALID_AUTH_TOKEN])
      else
        order
      end
    end
    
    def get_and_authenticate_order
      authorize_order!(fetch_order_by_uuid)
    end
    
    def invalid_date_error
      halt 400, error_object("Invalid date", "Couldn't parse date given by before param", ERROR::CODES[:INVALID_DATE])
    end

    def sequence_number_not_found_error
      halt 404, error_object("Sequence number not found", "Sent order with that tx sequence number not found", ERROR::CODES[:SEQUENCE_NUMBER_NOT_FOUND])
    end
    
    def uuid_not_found_error
      halt 404, error_object("UUID not found", "UUID #{params[:uuid]} not found", ERROR::CODES[:ORDER_NOT_FOUND])
    end
    
    def message_missing_error
      halt 400, error_object("Message upload problem", "Either a message file or a message parameter is required", ERROR::CODES[:MESSAGE_MISSING])
    end
    
    def message_file_missing_error
      halt 400, error_object("Message upload problem", "No tempfile received", ERROR::CODES[:FILE_MISSING])
    end

    def message_file_too_large_error
      halt 413, error_object("Message upload problem", "Message size exceeds max size #{MAX_MESSAGE_SIZE}", ERROR::CODES[:MESSAGE_FILE_TOO_LARGE])
    end
    
    def message_file_too_small_error
      halt 400, error_object("Message upload problem", "Message too small. Minimum message size is #{MIN_MESSAGE_SIZE} byte", ERROR::CODES[:MESSAGE_FILE_TOO_SMALL])
    end

    def bid_too_small_error(min_bid)
      halt 413, error_object("Bid too low", "Per byte bid cannot be below #{MIN_PER_BYTE_BID} millisatoshis per byte. The minimum bid for this message is #{min_bid} millisatoshis.", ERROR::CODES[:BID_TOO_SMALL])
    end
    
    def order_bump_error(order)
      halt 400, error_object("Cannot bump order", "Order already #{order.status}", ERROR::CODES[:ORDER_BUMP_ERROR])
    end
    
    def order_cancellation_error(order)
      halt 400, error_object("Cannot cancel order", "Order already #{order.status}", ERROR::CODES[:ORDER_CANCELLATION_ERROR])
    end

  end
  helpers OrderHelpers
end
