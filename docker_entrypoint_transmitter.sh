#!/bin/bash
set -eo pipefail

if [ ! -f /data/ionosphere/ionosphere_production.sqlite3 ]; then
        bundle exec rake db:create
        bundle exec rake db:schema:load
fi

echo "starting transmitter"
bundle exec ruby daemons/transmitter.rb

# shutdown the entire process when any of the background jobs exits (even if successfully)
wait -n
kill -TERM $$
