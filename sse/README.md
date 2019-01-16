# Redis to SSE

Subscribes to a redis pub/sub channel and broadcasts messages
over HTTP server-sent events.

To start the server:

```bash
$ git clone git@github.com:shesek/redis-to-sse && cd redis-to-sse
$ npm install
$ REDIS_URI=redis://127.0.0.1:6379 SUB_TOPIC=foobar PORT=4500 npm start
```

To subscribe to events, send a GET request to `/stream`.
