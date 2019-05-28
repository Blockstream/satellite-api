# Satellite API

A lightning app (Lapp) based on c-lightning. Presents an API to submit messages for global broadcast over Blockstream Satellite and pay for them with Bitcoin Lightning payments.

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-generate-toc again -->
## Contents

- [Setup](#setup)
- [Run](#run)
- [Example Applications](#example-applications)
- [REST API](#rest-api)
    - [POST /order](#post-order)
    - [POST /order/:uuid/bump](#post-orderuuidbump)
    - [GET /order/:uuid](#get-orderuuid)
    - [GET /order/:uuid/sent_message](#get-orderuuidsentmessage)
    - [DELETE /order/:uuid](#delete-orderuuid)
    - [GET /orders/pending](#get-orderspending)
    - [GET /orders/queued](#get-ordersqueued)
    - [GET /orders/sent](#get-orderssent)
    - [GET /info](#get-info)
    - [GET /subscribe/:channels](#get-subscribechannels)
- [Debugging](#debugging)
    - [Queue Page](#queue-page)
- [Future Work](#future-work)

<!-- markdown-toc end -->

## Setup

The Blockstream Satellite API is dependent on [lightning-charge](https://github.com/ElementsProject/lightning-charge), which itself is dependent on [c-lightning](https://github.com/ElementsProject/lightning) and [bitcoin](https://github.com/bitcoin/bitcoin). To bring up charged, lightningd, and bitcoind, a [handy docker-compose](https://github.com/DeviaVir/blc-docker) script is available.

The satellite API itself is comprised of a RESTful API server and a transmitter daemon. The API server speaks JSON and is used for creating and managing message transmission orders and for processing lightning-charge payment callbacks. The transmitter daemon dequeues paid orders and writes the uploaded message a named pipe, where they are subsequently processed by the Blockstream Satellite GNU Radio transmitter.

## Run ##

The included `Dockerfile` builds a Docker file with the necessary gem dependencies, directory structure, and permissions. The included `docker_entrypoint.sh` runs the API server and transmitter daemon.

After building a Docker image (`satellite_api` in the example below), decide where you are going to keep your persisted data (`~/docker/data` in the example below) and run it like this:

```bash
docker run -e CHARGE_ROOT=http://api-token:mySecretToken@localhost:9112 -e CALLBACK_URI_ROOT=http://my.public.ip:9292 -u `id -u` -v ~/docker/data:/data -p 9292:9292 -it satellite_api
```

To run in developer mode, set the `RACK_ENV` environment variable like this:

```bash
docker run -e CHARGE_ROOT=http://api-token:mySecretToken@localhost:9112 -e CALLBACK_URI_ROOT=http://my.public.ip:9292 -e RACK_ENV=development -u `id -u` -v ~/docker/data:/data -p 9292:9292 -it satellite_api
```

## Example Applications

Example Python applications are available at the [Blockstream Satellite examples directory](https://github.com/Blockstream/satellite/tree/master/api/examples) as a reference regarding how to implement the interaction with the API. There is one application specifically for sending data to the API, called "API data sender", and another application for reading the API data acquired by the Blockstream Satellite receiver, called "API data reader". Additionally, there is one application that allows testing API data reception directly through the internet, without the actual satellite receiver hardware, called "demo receiver". Refer to the documentation in the given link.

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

Error codes that can be returned by this endpoint include: `BID_TOO_SMALL` (102), `FILE_MISSING` (103), `MESSAGE_FILENAME_MISSING` (116), `MESSAGE_FILE_TOO_SMALL` (117), `MESSAGE_FILE_TOO_LARGE` (118), `BID_TOO_SMALL` (102), `MESSAGE_TOO_LONG` (125), `MESSAGE_MISSING` (126).

### POST /order/:uuid/bump ###

Increase the bid for an order sitting in the transmission queue. The `bid_increase` must be provided in the body of the POST. A Lightning invoice is returned for it and, when it is paid, the increase is added to the current bid. An `auth_token` must also be provided. For example, to increase the bid on the order placed above by 100,000 millisatoshis, issue a POST like this:

```bash
curl -v -F "bid_increase=100000" -F "auth_token=d784e322dad7ec2671086ce3ad94e05108f2501180d8228577fbec4115774750" $SATELLITE_API/order/409348bc-6af0-4999-b715-4136753979df/bump
```

Response object is in the same format as for `POST /order`.

As shown below for DELETE, the `auth_token` may alternatively be provided using the `X-Auth-Token` HTTP header.

Error codes that can be returned by this endpoint include: `INVALID_AUTH_TOKEN` (109), `ORDER_NOT_FOUND` (104), `BID_INCREASE_MISSING` (105), `ORDER_BUMP_ERROR` (119).

### GET /order/:uuid ###

Retrieve an order by UUID. Must provide the corresponding auth token to prove that it is yours.

```bash
curl -v -H "X-Auth-Token: 5248b13a722cd9b2e17ed3a2da8f7ac6bd9a8fe7130357615e074596e3d5872f" $SATELLITE_API/order/409348bc-6af0-4999-b715-4136753979df
```

Error codes that can be returned by this endpoint include: `INVALID_AUTH_TOKEN` (109), `ORDER_NOT_FOUND` (104).

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

### GET /orders/pending  ###

Retrieve a list of 20 orders awaiting payment ordered by creation time. For pagination, optionally specify a `before` parameter (in ISO 8601 format) that specifies that the 20 orders immediately prior to the given time be returned.

```bash
curl $SATELLITE_API/orders/pending
```

```bash
curl $SATELLITE_API/orders/pending?before=2019-01-16T18:13:46-08:00
```

The response is a JSON array of records (one for each queued message). The revealed fields for each record include: `uuid`, `bid`, `bid_per_byte`, `message_size`, `message_digest`, `status`, `created_at`, `started_transmission_at`, and `ended_transmission_at`.

Error codes that can be returned by this endpoint include: `INVALID_DATE` (113).

### GET /orders/queued  ###

Retrieve a list of paid, but unsent orders in descending order of bid-per-byte. Both pending orders and the order currently being transmitted are returned. Optionally, accepts a parameter specifying how many queued order to return.

```bash
curl $SATELLITE_API/orders/queued
```

```bash
curl $SATELLITE_API/orders/queued?limit=18
```

The response is a JSON array of records (one for each queued message). The revealed fields for each record include: `uuid`, `bid`, `bid_per_byte`, `message_size`, `message_digest`, `status`, `created_at`, `started_transmission_at`, and `ended_transmission_at`.

Error codes that can be returned by this endpoint include: `LIMIT_TOO_LARGE` (101).

### GET /orders/sent  ###

Retrieves a list of up to 20 sent orders in reverse chronological order. For pagination, optionally specify a `before` parameter (in ISO 8601 format) that specifies that the 20 orders immediately prior to the given time be returned.

```bash
curl $SATELLITE_API/orders/sent
```

```bash
curl $SATELLITE_API/orders/sent?before=2019-01-16T18:13:46-08:00
```

The response is a JSON array of records (one for each queued message). The revealed fields for each record include: `uuid`, `bid`, `bid_per_byte`, `message_size`, `message_digest`, `status`, `created_at`, `started_transmission_at`, and `ended_transmission_at`.

Error codes that can be returned by this endpoint include: `INVALID_DATE` (113).

### GET /info

Returns information about the c-lightning node where satellite API payments are terminated. The response is a JSON object consisting of the node ID, port, IP addresses, and other information useful for opening payment channels. For example:

```bash
{"id":"032c6ba19a2141c5fee6ac8b6ff6cf24456fd4e8e206716a39af3300876c3a4835","port":42259,"address":[],"version":"v0.5.2-2016-11-21-1937-ge97ee3d","blockheight":434,"network":"regtest"}
```

### GET /subscribe/:channels

Subscribe to one or more [server-sent events](https://en.wikipedia.org/wiki/Server-sent_events) channels. The `channels` parameter is a comma-separated list of event channels. Currently, only one channel is available: `transmissions`, to which an event is pushed each time a message transmission begins and ends. Event data includes a JSON representation of the order, including its current status.

```bash
curl $SATELLITE_API/subscribe/:channels
```

Error codes that can be returned by this endpoint include: `CHANNELS_EQUALITY` (124).

## Debugging ##

### Queue Page ###

For debugging and as an example of how to build a web front-end to the satellite API, there is a simple table view of queued, pending, and sent messages at `$SATELLITE_API/queue.html`

## Future Work ##

* Configure `Rack::Attack` or similar to block and throttle abusive requests.
* Support bids priced in fiat currencies.
* Report the top bid_per_byte, queue depth, and estimated time to transmit in the response to `POST /order`.
