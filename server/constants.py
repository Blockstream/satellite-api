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


ORDER_FETCH_STATES = [
    'pending', 'paid', 'transmitting', 'confirming', 'queued', 'sent',
    'rx-pending', 'received', 'retransmitting'
]


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
DEFAULT_TX_CONFIRM_TIMEOUT_SECS = 60

SERVER_PORT = 9292
CALLBACK_URI_ROOT = os.getenv('CALLBACK_URI_ROOT',
                              "http://127.0.0.1:{}".format(SERVER_PORT))
CHARGE_API_TOKEN = os.getenv('CHARGE_API_TOKEN', str(uuid.uuid4()))
LIGHTNING_WEBHOOK_KEY = hmac_sha256_digest('charged-token', CHARGE_API_TOKEN)

CHARGE_ROOT = os.getenv('CHARGE_ROOT',
                        f'http://api-token:{CHARGE_API_TOKEN}@127.0.0.1:9112')
CONNECTION_TIMEOUT = 2
DB_FILE = db_conf[env]['database']
DB_ROOT = os.path.dirname(DB_FILE)
LN_INVOICE_EXPIRY = 60 * 60  # one hour
LN_INVOICE_DESCRIPTION = 'Blockstream Satellite Transmission' if os.getenv(
    'ENV') == 'production' else 'BSS Test'

DEFAULT_MAX_MESSAGE_SIZE = 2**20
MAX_TEXT_MSG_LEN = 1024  # valid for message (not file)

MIN_BID = int(os.getenv('MIN_BID', 1000))
MIN_MESSAGE_SIZE = 1
MIN_PER_BYTE_BID = float(os.getenv('MIN_PER_BYTE_BID', 1))
MSG_STORE_PATH = os.path.join(DB_ROOT, 'messages')
PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
RESPONSE_TIMEOUT = 2

FORCE_PAYMENT = os.getenv('FORCE_PAYMENT', False)

LOGGING_FORMAT = '%(asctime)s %(levelname)s %(name)s : %(message)s'
REDIS_URI = os.getenv('REDIS_URI', 'redis://127.0.0.1:6379')

USER_CHANNEL = 1
AUTH_CHANNEL = 3
GOSSIP_CHANNEL = 4
BTC_SRC_CHANNEL = 5


class ChannelInfo:

    def __init__(self,
                 name,
                 user_permissions,
                 tx_rate,
                 max_msg_size,
                 tx_confirm_timeout_secs=DEFAULT_TX_CONFIRM_TIMEOUT_SECS):
        """Construct channel information

        Args:
            name (str): Channel name.
            user_permissions (list): User permissions. An empty list means the
                channel messages are only sent over satellite. A list with
                'get' permission only means the users can only fetch messages
                but not post them, and only the admin can post messages.
            tx_rate (float): Transmit rate in bytes/sec. Used to handle the
                retransmission timeout intervals independently on each channel.
            max_msg_size (int): Maximum message size on this channel.
            tx_confirm_timeout_secs (int): Tx confirmation timeout in seconds
                leading to retransmission decisions.
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
        self.tx_rate = tx_rate
        self.max_msg_size = max_msg_size
        self.tx_confirm_timeout_secs = tx_confirm_timeout_secs


CHANNEL_INFO = {
    USER_CHANNEL:
    ChannelInfo('transmissions', ['get', 'post', 'delete'], 1000,
                DEFAULT_MAX_MESSAGE_SIZE),
    AUTH_CHANNEL:
    ChannelInfo('auth', [], 125, DEFAULT_MAX_MESSAGE_SIZE),
    GOSSIP_CHANNEL:
    ChannelInfo(
        'gossip',
        ['get'],
        500,
        1800000,  # tx over 1h at 500 bytes/sec
        300  # Tx confirmation timeout = 5 min
    ),
    BTC_SRC_CHANNEL:
    ChannelInfo(
        'btc-src',
        ['get'],
        500,
        16200000,  # tx over 9h at 500 bytes/sec
        300  # Tx confirmation timeout = 5 min
    ),
}

CHANNELS = list(CHANNEL_INFO.keys())
