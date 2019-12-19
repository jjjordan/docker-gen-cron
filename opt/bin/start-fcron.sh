#!/bin/sh

. /opt/bin/fcron.sh

# Start reload signal handler
exec /opt/lib/waitsig.py
