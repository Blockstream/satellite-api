from math import ceil
from constants import MIN_BID, MIN_PER_BYTE_BID

ETH_MTU = 1500
UDP_IP_HEADER = 20 + 8
BLOCKSAT_HEADER = 8
MPE_HEADER = 16
MAX_BLOCKSAT_PAYLOAD = ETH_MTU - (UDP_IP_HEADER + BLOCKSAT_HEADER)


def calc_ota_msg_len(msg_len):
    """Compute the number of bytes sent over-the-air (OTA) for an API message

    API messages are carried by Blocksat Packets, sent in the payload of UDP
    datagrams over IPv4, with a layer-2 MTU of 1500 bytes, and, ultimately,
    transported over MPE. If the message size is such that the UDP/IPv4 packet
    exceeds the layer-2 MTU, fragmentation is not handled at the IP level but
    instead at application layer, i.e., at the Blocksat Packet protocol level.

    Args:
        msg_len : Length of the API message to be transmitted

    """
    # Is it going to be fragmented?
    n_frags = ceil(msg_len / MAX_BLOCKSAT_PAYLOAD)

    # Including all fragments, considering the Blocksat + UDP + IPv4 + MPE
    # layers, the total overhead becomes:
    total_overhead = (MPE_HEADER + UDP_IP_HEADER + BLOCKSAT_HEADER) * n_frags

    return total_overhead + msg_len


def get_min_bid(data_len):
    ota_msg_len = calc_ota_msg_len(data_len)
    return max(ceil(ota_msg_len * MIN_PER_BYTE_BID), MIN_BID)


def validate_bid(data_len, bid):
    min_bid = get_min_bid(data_len)
    return bid >= min_bid
