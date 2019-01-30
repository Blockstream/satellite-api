ENV['RACK_ENV'] ||= 'development'
KILO_BYTE = 2 ** 10
MEGA_BYTE = 2 ** 20
ONE_HOUR = 60 * 60
ONE_DAY = 24 * ONE_HOUR
ONE_MONTH = 31 * ONE_DAY

require 'yaml'
yaml_path = File.join(File.expand_path(File.dirname(__FILE__)), 'config', 'database.yml')
conf = YAML.load_file(yaml_path)
DB_ROOT = File.dirname(conf[ENV['RACK_ENV']]['database'])
MESSAGE_STORE_PATH = File.join(DB_ROOT, 'messages')

CALLBACK_URI_ROOT = ENV['CALLBACK_URI_ROOT'] || "http://localhost:4567"

CHARGE_API_TOKEN = ENV['CHARGE_API_TOKEN'] || 'mySecretToken'
CHARGE_ROOT = ENV['CHARGE_ROOT'] || "http://api-token:#{CHARGE_API_TOKEN}@localhost:9112"

MIN_PER_BYTE_BID = Integer(ENV['MIN_PER_BYTE_BID'] || 50) # minimum price per byte in millisatoshis
MIN_MESSAGE_SIZE = 1

FRAGMENT_SIZE = 2 * KILO_BYTE
FRAMING_OVERHEAD_PER_FRAGMENT = 16

TRANSMIT_RATE = Integer(ENV['TRANSMIT_RATE'] || KILO_BYTE) # bytes per second
MAX_HEAD_OF_LINE_BLOCKING_TIME = 10 # more than 10 seconds and it doesn't feel "instant"
MAX_MESSAGE_SIZE = MAX_HEAD_OF_LINE_BLOCKING_TIME * TRANSMIT_RATE

LN_INVOICE_EXPIRY = ONE_HOUR
LN_INVOICE_DESCRIPTION = (ENV['RACK_ENV'] == 'production') ? "Blockstream Satellite Transmission" : "BSS Test"
MAX_LIGHTNING_INVOICE_SIZE = 1024

EXPIRE_PENDING_ORDERS_AFTER = ONE_DAY
MESSAGE_FILE_RETENTION_TIME = ONE_MONTH

PAGE_SIZE = 20
MAX_QUEUED_ORDERS_REQUEST = 100

REDIS_URI = ENV['REDIS_URI'] || "redis://127.0.0.1:6379"

