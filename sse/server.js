// Setup redis
const redis = require('redis').createClient(process.env.REDIS_URI),
	  channels = process.env.SUB_CHANNELS.split(',')

console.log(`Subscribing to Redis on ${channels.join(',')}`)
channels.forEach(chan => redis.subscribe(chan))

// Log messages and number of SSE subscribers
redis.on('message', (chan, msg) => console.log(`Broadcasting ${chan}: ${msg}`))
setInterval(_ => console.log(`Total subscribers: ${ redis.listenerCount('message') - 1 }`), 60000)

// Setup express server
const app = require('express')()
app.set('trust proxy', process.env.PROXIED || 'loopback')
app.use(require('morgan')('dev'))

// SSE endpoint
app.get('/stream', (req, res) => {
    const subscriptions = req.query.channels && req.query.channels.split(',')
    console.log(`New subscriber for ${ subscriptions ? subscriptions.join(',') : 'all channels' }`)

    res.set({
        'X-Accel-Buffering': 'no',
        'Cache-Control': 'no-cache',
        'Content-Type': 'text/event-stream',
        'Connection': 'keep-alive'
    }).flushHeaders()

    function onMsg (chan, msg) {
        if (!subscriptions || subscriptions.includes(chan)) {
            res.write(`event:${chan}\ndata:${msg}\n\n`)
        }
    }
    redis.on('message', onMsg)

    const keepAlive = setInterval(_ => res.write(': keepalive\n\n'), 25000)

    req.once('close', _ => (redis.removeListener('message', onMsg),
                            clearInterval(keepAlive),
                            console.log('Subscriber disconnected')))
})

app.listen(
    process.env.PORT || 4500,
    function() { console.log(`HTTP server running on ${this.address().address}:${this.address().port}`) }
)
