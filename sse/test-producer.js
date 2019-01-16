const redis = require('redis').createClient(process.env.REDIS_URI)

const chan = process.env.PUB_CHANNEL

let i = 0
setInterval(_ => redis.publish(chan, JSON.stringify({ foo: 'bar', i: ++i })), 1000)
