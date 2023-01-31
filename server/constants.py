import os
import uuid
import yaml
from enum import Enum

from utils import hmac_sha256_digest


class OrderStatus(Enum):
    pending = 0
    paid = 1
    transmitting = 2
    sent = 3
    received = 4
    cancelled = 5
    expired = 6
    confirming = 7  # confirming Tx (between transmitting and sent)


class InvoiceStatus(Enum):
    pending = 0
    paid = 1
    expired = 2


db_yaml_path = os.path.join("config", 'database.yml')
with open(db_yaml_path, 'r') as fd:
    db_conf = yaml.safe_load(fd)

env = os.getenv('ENV', 'development')

EXPIRE_PENDING_ORDERS_AFTER_DAYS = 1
MESSAGE_FILE_RETENTION_TIME_DAYS = 31
TX_CONFIRM_TIMEOUT_SECS = 60

SERVER_PORT = 9292
CALLBACK_URI_ROOT = os.getenv('CALLBACK_URI_ROOT',
                              "http://localhost:{}".format(SERVER_PORT))
CHARGE_API_TOKEN = os.getenv('CHARGE_API_TOKEN', str(uuid.uuid4()))
LIGHTNING_WEBHOOK_KEY = hmac_sha256_digest('charged-token', CHARGE_API_TOKEN)

CHARGE_ROOT = os.getenv('CHARGE_ROOT',
                        f'http://api-token:{CHARGE_API_TOKEN}@localhost:9112')
CONNECTION_TIMEOUT = 2
DB_FILE = db_conf[env]['database']
DB_ROOT = os.path.dirname(DB_FILE)
LN_INVOICE_EXPIRY = 60 * 60  # one hour
LN_INVOICE_DESCRIPTION = 'Blockstream Satellite Transmission' if os.getenv(
    'ENV') == 'production' else 'BSS Test'

MAX_MESSAGE_SIZE = 2**20
MAX_TEXT_MSG_LEN = 1024  # valid for message (not file)

MIN_BID = int(os.getenv('MIN_BID', 1000))
MIN_MESSAGE_SIZE = 1
MIN_PER_BYTE_BID = float(os.getenv('MIN_PER_BYTE_BID', 1))
MSG_STORE_PATH = os.path.join(DB_ROOT, 'messages')
PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
RESPONSE_TIMEOUT = 2

FORCE_PAYMENT = os.getenv('FORCE_PAYMENT', False)

DEFAULT_TX_RATE = 1000  # bytes per second
TRANSMIT_RATE = int(os.getenv('TRANSMIT_RATE',
                              DEFAULT_TX_RATE))  # bytes per second

LOGGING_FORMAT = '%(asctime)s %(levelname)s %(name)s : %(message)s'
REDIS_URI = os.getenv('REDIS_URI', 'redis://127.0.0.1:6379')

USER_CHANNEL = 1
AUTH_CHANNEL = 3
GOSSIP_CHANNEL = 4
BTC_SRC_CHANNEL = 5


class ChannelInfo:

    def __init__(self, name, user_permissions):
        """Construct channel information

        Args:
            name (str): Channel name.
            user_permissions (list): User permissions. An empty list means the
                channel messages are only sent over satellite. A list with
                'get' permission only means the users can only fetch messages
                but not post them, and only the admin can post messages.
        """
        assert isinstance(user_permissions, list)
        assert len(user_permissions) == 0 or \
            [x in ['get', 'post'] for x in user_permissions]
        self.name = name
        self.user_permissions = user_permissions
        # Attribute indicating whether the channel messages must be paid by the
        # user. The channels on which users can post messages necessarily
        # require payment. The other channels can only have messages posted by
        # the admin, and these messages are not paid.
        self.requires_payment = 'post' in user_permissions


CHANNEL_INFO = {
    USER_CHANNEL: ChannelInfo('transmissions', ['get', 'post', 'delete']),
    AUTH_CHANNEL: ChannelInfo('auth', []),
    GOSSIP_CHANNEL: ChannelInfo('gossip', ['get']),
    BTC_SRC_CHANNEL: ChannelInfo('btc-src', ['get']),
}

CHANNELS = list(CHANNEL_INFO.keys())
