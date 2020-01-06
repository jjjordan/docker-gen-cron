#!/bin/sh

# Set timezone
if [ -n "$TZ" ]; then
	rm -f /etc/localtime
	cp /usr/share/zoneinfo/$TZ /etc/localtime || exit $?
	echo $TZ > /etc/timezone
fi

# Setup requisite files
cp /opt/etc/fcron.conf /usr/local/etc/fcron.conf
chown root:fcron /usr/local/etc/fcron.conf
chmod 640 /usr/local/etc/fcron.conf

mkdir -p /var/spool/fcron
chown fcron:fcron /var/spool/fcron
chmod 770 /var/spool/fcron

# Remove pidfiles
rm -f /var/run/fcron.pid /var/run/fcron.fifo

# Start fcron
fcron -f --nosyslog &
