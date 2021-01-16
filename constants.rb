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

MIN_PER_BYTE_BID = Integer(ENV['MIN_PER_BYTE_BID'] || 1) # minimum price per byte in millisatoshis
MIN_MESSAGE_SIZE = 1

UDP_HDR_SIZE         = 8
BLOCKSAT_HDR_SIZE    = 8
IP_HDR_SIZE          = 20
MPE_HDR_SIZE         = 16
L3_OVERHEAD          = BLOCKSAT_HDR_SIZE + UDP_HDR_SIZE + IP_HDR_SIZE
L2_OVERHEAD          = L3_OVERHEAD + MPE_HDR_SIZE
L2_MTU               = 1500
MAX_BLOCKSAT_PAYLOAD = L2_MTU - L3_OVERHEAD

DEFAULT_TX_RATE = 1000 # bytes per second
TRANSMIT_RATE = Integer(ENV['TRANSMIT_RATE'] || DEFAULT_TX_RATE) # bytes per second
MAX_HEAD_OF_LINE_BLOCKING_TIME = 1050 # max duration (secs) over which the tx link can be blocked by a message
MAX_MESSAGE_SIZE = MAX_HEAD_OF_LINE_BLOCKING_TIME * TRANSMIT_RATE

LN_INVOICE_EXPIRY = ONE_HOUR
LN_INVOICE_DESCRIPTION = (ENV['RACK_ENV'] == 'production') ? "Blockstream Satellite Transmission" : "BSS Test"
MAX_LIGHTNING_INVOICE_SIZE = 1024

EXPIRE_PENDING_ORDERS_AFTER = ONE_DAY
MESSAGE_FILE_RETENTION_TIME = ONE_MONTH

PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

REDIS_URI = ENV['REDIS_URI'] || "redis://127.0.0.1:6379"
