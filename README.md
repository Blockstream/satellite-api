# Satellite API

[![Tests](https://github.com/Blockstream/satellite-api/actions/workflows/test.yml/badge.svg?branch=master)](https://github.com/Blockstream/satellite-api/actions/workflows/test.yml)

A lightning app (Lapp) based on c-lightning. Presents an API to submit messages for global broadcast over Blockstream Satellite with payments via Bitcoin Lightning.

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-generate-toc again -->

- [Satellite API](#satellite-api)
  - [Setup](#setup)
  - [Run](#run)
  - [Example Applications](#example-applications)
  - [REST API](#rest-api)
    - [POST /order](#post-order)
    - [POST /order/:uuid/bump](#post-orderuuidbump)
    - [GET /order/:uuid](#get-orderuuid)
    - [DELETE /order/:uuid](#delete-orderuuid)
    - [GET /orders/:state](#get-ordersstate)
    - [GET /message/:seq\_num](#get-messageseq_num)
    - [GET /info](#get-info)
    - [GET /subscribe/:channels](#get-subscribechannels)
    - [Queue Page](#queue-page)
  - [Future Work](#future-work)

<!-- markdown-toc end -->

## Setup

The Satellite API comprises a RESTful API server and a transmitter daemon. The API server speaks JSON and is used for creating and managing message transmission orders and for processing lightning-charge payment callbacks. The transmitter daemon continuously dequeues paid messages and coordinates the corresponding satellite transmissions.

The Blockstream Satellite API is dependent on [lightning-charge](https://github.com/ElementsProject/lightning-charge), which itself is dependent on [c-lightning](https://github.com/ElementsProject/lightning) and [bitcoin](https://github.com/bitcoin/bitcoin). The Satellite API server communicates with the Bitcoin Lightning Charge (BLC) stack to handle the Bitcoin Lightning payment required for each transmission order.

## Run ##

A docker-compose script is available to bring up the Satellite API server, the transmitter daemon, and the other dependencies (BLC and Redis). To launch the container stack, run:

```
docker-compose up
```

## Example Applications

The Blockstream Satellite command-line interface (CLI) has commands to submit messages to the Satellite API for global broadcasting. It also has commands to receive those messages through an actual satellite receiver or a simulated/demo receiver for testing. Please refer to the [CLI documentation](https://blockstream.github.io/satellite/doc/api.html). Alternatively, if you are interested in implementing the communication with the Satellite API from scratch, the referred CLI can be used as a reference. The source code is available on the [Satellite repository](https://github.com/Blockstream/satellite/tree/master/blocksatcli/api).

## REST API ##

Each call to an API endpoint responds with a JSON object, whether the call is successful or results in an error.

The code samples below assume that you've set `SATELLITE_API` in your shell to the public base URL of your server.

### POST /order ###

Place an order for a message transmission. The body of the POST must provide a `bid` in millisatoshis and a message, provided either as a `message` parameter string or as an HTTP form-based `file` upload. If the bid is below an allowed minimum millisatoshis per byte, a `BID_TOO_SMALL` (102) error is returned.

For example, to place an order to transmit the message "Hello world" with an initial bid of 10,000 millisatoshi, issue an HTTP POST request like this:

```bash
curl -F "bid=10000" -F "message=Hello World" $SATELLITE_API/order
```

Or, to place an order to transmit the file `hello_world.png` with an initial bid of 10,000 millisatoshi, issue an HTTP POST request like this:

```bash
curl -F "bid=10000" -F "file=@/path/to/upload/file/hello_world.png" $SATELLITE_API/order
```

If successful, the response includes the JSON Lightning invoice as returned by Lightning Charge's [POST /invoice](https://github.com/ElementsProject/lightning-charge#post-invoice) and an authentication token that can be used to modify the order. Within the metadata of the Lightning invoice, metadata is included providing: the bid (in millisatoshis), the SHA256 digest of the uploaded message file, and a UUID for the order.

```bash
{"auth_token":"d784e322dad7ec2671086ce3ad94e05108f2501180d8228577fbec4115774750","uuid":"409348bc-6af0-4999-b715-4136753979df","lightning_invoice":{"id":"N0LOTYc9j0gWtQVjVW7pK","msatoshi":"514200","description":"BSS Test","rhash":"5e5c9d111bc76ce4bf9b211f12ca2d9b66b81ae9839b4e530b16cedbef653a3a","payreq":"lntb5142n1pd78922pp5tewf6ygmcakwf0umyy039j3dndntsxhfswd5u5ctzm8dhmm98gaqdqdgff4xgz5v4ehgxqzjccqp286gfgrcpvzl04sdg2f9sany7ptc5aracnd6kvr2nr0e0x5ajpmfhsjkqzw679ytqgnt6w4490jjrgcvuemz790salqyz9far68cpqtgq3q23el","expires_at":1541642146,"created_at":1541641546,"metadata":{"sha256_message_digest":"0e2bddf3bba1893b5eef660295ef12d6fc72870da539c328cf24e9e6dbb00f00","uuid":"409348bc-6af0-4999-b715-4136753979df"},"status":"unpaid"}}
```

The error codes that can be returned by this endpoint include `BID_TOO_SMALL` (102), `MESSAGE_FILE_TOO_SMALL` (117), `MESSAGE_FILE_TOO_LARGE` (118), `MESSAGE_MISSING` (126), and `ORDER_CHANNEL_UNAUTHORIZED_OP` (130).

### POST /order/:uuid/bump ###

Increase the bid for an order sitting in the transmission queue. The `bid_increase` must be provided in the body of the POST. A Lightning invoice is returned for it and, when it is paid, the increase is added to the current bid. An `auth_token` must also be provided. For example, to increase the bid on the order placed above by 100,000 millisatoshis, issue a POST like this:

```bash
curl -v -F "bid_increase=100000" -F "auth_token=d784e322dad7ec2671086ce3ad94e05108f2501180d8228577fbec4115774750" $SATELLITE_API/order/409348bc-6af0-4999-b715-4136753979df/bump
```

Response object is in the same format as for `POST /order`.

As shown below for DELETE, the `auth_token` may alternatively be provided using the `X-Auth-Token` HTTP header.

The error codes that can be returned by this endpoint include `INVALID_AUTH_TOKEN` (109), `ORDER_NOT_FOUND` (104), and `ORDER_CHANNEL_UNAUTHORIZED_OP` (130).

### GET /order/:uuid ###

Retrieve an order by UUID. Must provide the corresponding auth token to prove that it is yours.

```bash
curl -v -H "X-Auth-Token: 5248b13a722cd9b2e17ed3a2da8f7ac6bd9a8fe7130357615e074596e3d5872f" $SATELLITE_API/order/409348bc-6af0-4999-b715-4136753979df
```

The error codes that can be returned by this endpoint include `INVALID_AUTH_TOKEN` (109), `ORDER_NOT_FOUND` (104), and `ORDER_CHANNEL_UNAUTHORIZED_OP` (130).

### DELETE /order/:uuid ###

To cancel an order, issue an HTTP DELETE request to the API endpoint `/order/:uuid/` providing the UUID of the order. An `auth_token` must also be provided. For example, to cancel the order above, issue a request like this:

```bash
curl -v -X DELETE -F "auth_token=5248b13a722cd9b2e17ed3a2da8f7ac6bd9a8fe7130357615e074596e3d5872f" $SATELLITE_API/order/409348bc-6af0-4999-b715-4136753979df
```

The `auth_token` may be provided as a parameter in the DELETE body as above or may be provided using the `X-Auth-Token` HTTP header, like this:

```bash
curl -v -X DELETE -H "X-Auth-Token: 5248b13a722cd9b2e17ed3a2da8f7ac6bd9a8fe7130357615e074596e3d5872f" $SATELLITE_API/order/409348bc-6af0-4999-b715-4136753979df
```

Error codes that can be returned by this endpoint include: `INVALID_AUTH_TOKEN` (109), `ORDER_NOT_FOUND` (104), `ORDER_CANCELLATION_ERROR` (120).

### GET /orders/:state  ###

Retrieve a list of up to 20 orders in a given state. The following states are supported:

| State            | Description                                                                                                |
| ---------------- | ---------------------------------------------------------------------------------------------------------- |
| `pending`        | Orders waiting for payment. Sorted by creation time.                                                       |
| `paid`           | Orders already paid and waiting for transmission. Sorted by creation time.                                 |
| `transmitting`   | Orders being transmitted over satellite. Sorted by the transmission start time.                            |
| `confirming`     | Orders whose transmissions are being confirmed (almost finished). Sorted by the transmission start time.   |
| `queued`         | Combination of orders in `paid`, `transmitting`, and `confirming` state. Sorted by the order creation time |
| `sent`           | Orders already transmitted. Sorted by the transmission end time.                                           |
| `rx-pending`     | Orders already transmitted but with pending Rx confirmations. Sorted by the transmission end time.         |
| `retransmitting` | Orders under retransmission in one or more regions. Sorted by the time of the last retransmission attempt. |
| `received`       | Orders completely transmitted and received in all targeted regions. Sorted by the transmission end time.   |

For example:
```bash
curl $SATELLITE_API/orders/pending
```

For pagination or time filtering, optionally specify the `before` and/or `after` parameters (in ISO 8601 format) so that only orders in that time range are returned.

```bash
curl $SATELLITE_API/orders/pending\?after=2023-02-10T00:00:00\&before=2023-02-10T23:59:59
```

Alternatively, specify the time range based on deltas in seconds relative to the current time. For instance, the following example returns the pending orders created within a window that starts two minutes ago and ends one minute ago.

```bash
curl $SATELLITE_API/orders/pending\?after_delta=120\&before_delta=60
```

The response is a JSON array of records (one for each queued message). The revealed fields for each record include: `uuid`, `bid`, `bid_per_byte`, `message_size`, `message_digest`, `status`, `created_at`, `started_transmission_at`, and `ended_transmission_at`.

### GET /message/:seq_num

Retrieve a transmitted message by its unique sequence number. For example:

```bash
curl -v $SATELLITE_API/message/3
```

The error codes that can be returned by this endpoint include `SEQUENCE_NUMBER_NOT_FOUND` (114) and `ORDER_CHANNEL_UNAUTHORIZED_OP` (130).

### GET /info

Returns information about the c-lightning node where satellite API payments are terminated. The response is a JSON object consisting of the node ID, port, IP addresses, and other information useful for opening payment channels. For example:

```bash
{"id":"032c6ba19a2141c5fee6ac8b6ff6cf24456fd4e8e206716a39af3300876c3a4835","port":42259,"address":[],"version":"v0.5.2-2016-11-21-1937-ge97ee3d","blockheight":434,"network":"regtest"}
```

### GET /subscribe/:channels

Subscribe to one or more [server-sent events](https://en.wikipedia.org/wiki/Server-sent_events) channels. The `channels` parameter is a comma-separated list of event channels. Currently, the following channels are available: `transmissions`, `auth`, `gossip`, and `btc-src`. An event is broadcast on a channel each time a message transmission begins and ends on that channel. The event data consists of the order's JSON representation, including its current status.

```bash
curl $SATELLITE_API/subscribe/:channels
```

### Queue Page ###

A simple table view of queued, pending and sent messages is available at `$SATELLITE_API/queue.html`. This page can be used for debugging and as an example for building a web front-end to the satellite API.

## Future Work ##

* Configure `Flask-Limiter` or similar to block and throttle abusive requests.
* Support bids priced in fiat currencies.
* Report the top `bid_per_byte`, queue depth, and estimated time to transmit in the response of `POST /order`.
