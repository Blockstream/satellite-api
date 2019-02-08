require 'sinatra'
require 'sinatra/param'

require_relative 'constants'

set :raise_sinatra_param_exceptions, true

def error_object(title, detail, code)
  {:message => title, 
   :errors => [{
     title: title,
     detail: detail,
     code: code
     }]
   }.to_json
end

class ERROR
  CODES = {
    OTHER_ERROR: 1,
    PARAM_COERCION: 2,
    PARAM_MISSING: 3,
    PARAM_BLANK: 4,
    PARAM_NOT_STRING: 5,
    PARAM_FORMAT: 6,
    PARAM_EQUALITY: 7,
    PARAM_OUT_OF_RANGE: 8,
    PARAM_TOO_SMALL: 9,
    PARAM_TOO_LARGE: 10,
    PARAM_TOO_SHORT: 11,
    PARAM_TOO_LONG: 12,
    PARAM_ONE_OF: 13,
    PARAM_ANY_OF: 14,
    
    LIMIT_TOO_LARGE: 101,
    BID_TOO_SMALL: 102,
    FILE_MISSING: 103,
    ORDER_NOT_FOUND: 104,
    BID_INCREASE_MISSING: 105,
    BID_INCREASE_TOO_SMALL: 106,
    LID_MISSING: 107,
    CHARGED_AUTH_TOKEN_MISSING: 108,
    INVALID_AUTH_TOKEN: 109,
    LIGHTNING_CHARGE_INVOICE_ERROR: 110,
    LIGHTNING_CHARGE_WEBHOOK_REGISTRATION_ERROR: 111,
    INVOICE_ID_NOT_FOUND_ERROR: 112,
    INVALID_DATE: 113,
    SEQUENCE_NUMBER_NOT_FOUND: 114,
    MESSAGE_FILE_MISSING: 115,
    MESSAGE_FILENAME_MISSING: 116,
    MESSAGE_FILE_TOO_SMALL: 117,
    MESSAGE_FILE_TOO_LARGE: 118,
    ORDER_BUMP_ERROR: 119,
    ORDER_CANCELLATION_ERROR: 120,
    INVOICE_NOT_FOUND: 121,
    ORPHANED_INVOICE: 122,
    ORDER_ALREADY_PAID: 123,
    CHANNELS_EQUALITY: 124
  }
  
  def self.code(p, e)
    param = p.to_s.upcase
    error = e.to_s.upcase
    param_specific_error_code = "#{param}_#{error}".to_sym
    generic_error_code = "PARAM_#{error}".to_sym
    CODES[param_specific_error_code] || CODES[generic_error_code] || CODES[:OTHER_ERROR]
  end
end

error Sinatra::Param::ParameterCoercionError do
  param_name = env['sinatra.error'].param
  error_object("#{param_name} type coercion error", 
               "#{param_name} not the expected type",
               ERROR.code(param_name, :COERCION))
end

error Sinatra::Param::ParameterMissingError do
  param_name = env['sinatra.error'].param
  error_object("#{param_name} missing", 
               "#{param_name} is required and is missing",
               ERROR.code(param_name, :MISSING))
end

error Sinatra::Param::ParameterBlankError do
  param_name = env['sinatra.error'].param
  error_object("#{param_name} blank", 
               "#{param_name} cannot be blank",
               ERROR.code(param_name, :BLANK))
end

error Sinatra::Param::ParameterNotStringError do
  param_name = env['sinatra.error'].param
  error_object("#{param_name} must be a string", 
               "#{param_name} must be a string if using format validation #{env['sinatra.error'].options[:format]}",
               ERROR.code(param_name, :STRING))
end

error Sinatra::Param::ParameterFormatError do
  param_name = env['sinatra.error'].param
  error_object("#{param_name} must match format", 
               "#{param_name} must match format #{env['sinatra.error'].options[:format]}",
               ERROR.code(param_name, :FORMAT))
end

error Sinatra::Param::ParameterEqualityError do
  param_name = env['sinatra.error'].param
  error_object("#{param_name} must be value", 
               "#{param_name} must be #{env['sinatra.error'].options[:is]}",
               ERROR.code(param_name, :EQUALITY))
end

error Sinatra::Param::ParameterOutOfRangeError do
  param_name = env['sinatra.error'].param
  range = env['sinatra.error'].options[:in] || env['sinatra.error'].options[:within] || env['sinatra.error'].options[:range]
  error_object("#{param_name} out of range", 
               "#{param_name} out of range #{range}",
               ERROR.code(param_name, :EQUALITY))
end

error Sinatra::Param::ParameterTooSmallError do
  param_name = env['sinatra.error'].param
  error_object("#{param_name} too small", 
               "#{param_name} cannot be smaller than #{env['sinatra.error'].options[:min]}",
               ERROR.code(param_name, :TOO_SMALL))
end

error Sinatra::Param::ParameterTooLargeError do
  param_name = env['sinatra.error'].param
  error_object("#{param_name} too large", 
               "#{param_name} cannot be larger than #{env['sinatra.error'].options[:max]}",
               ERROR.code(param_name, :TOO_LARGE))
end

error Sinatra::Param::ParameterTooShortError do
  param_name = env['sinatra.error'].param
  error_object("#{param_name} too short", 
               "#{param_name} cannot have length less than #{env['sinatra.error'].options[:min_length]}",
               ERROR.code(param_name, :TOO_SHORT))
end

error Sinatra::Param::ParameterTooLongError do
  param_name = env['sinatra.error'].param
  error_object("#{param_name} too long", 
               "#{param_name} cannot have length greater than #{env['sinatra.error'].options[:max_length]}",
               ERROR.code(param_name, :TOO_LONG))
end
