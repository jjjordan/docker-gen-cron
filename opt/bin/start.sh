#!/bin/sh

rm -f /var/run/jobs.json
. /opt/bin/fcron.sh

if [ -n "$PREFIX" ]; then
	export DOCKER_GEN_CRON_PREFIX=$PREFIX
fi

if [ -n "$DEBUG" ]; then
	export DOCKER_GEN_CRON_DEBUG=$DEBUG
fi

# Start docker-gen after delay
sleep 1
exec docker-gen -config /opt/etc/jobs.cfg
