#!/bin/bash
set -eo pipefail

# create or migrate the db (if needed)
if [ ! -f /data/ionosphere/ionosphere_production.sqlite3 ]; then
        bundle exec rake db:create
        bundle exec rake db:schema:load
fi
bundle exec rake db:migrate

bundle exec rackup --host 0.0.0.0

# shutdown the entire process when any of the background jobs exits (even if successfully)
wait -n
kill -TERM $$
