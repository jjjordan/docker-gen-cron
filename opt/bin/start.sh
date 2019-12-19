#!/bin/sh

rm -f /var/run/jobs.json
. /opt/bin/fcron.sh

# Start docker-gen after delay
sleep 3
exec docker-gen -config /opt/etc/jobs.cfg $*
