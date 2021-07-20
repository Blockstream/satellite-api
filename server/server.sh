#!/bin/bash
set -e

# Run database migrations
alembic upgrade head

# Start the server
# set number of worker based on suggestion in:
# https://docs.gunicorn.org/en/stable/design.html#how-many-workers
n_cores=$(nproc --all)
n_workers=$(expr $n_cores \* 2 + 1)
gunicorn \
	--bind 0.0.0.0:9292 \
	--workers=$n_workers \
	--worker-class=gevent \
	--access-logfile=- \
	--access-logformat='%(t)s "%(r)s" %(s)s' \
	"server:create_app()"
