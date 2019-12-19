#!/bin/sh

# Set timezone
if [ -n "$TIMEZONE" ]; then
	rm -f /etc/localtime
	ln -fs /usr/share/zoneinfo/$TIMEZONE /etc/localtime || exit $?
	dpkg-reconfigure -f noninteractive tzdata
fi

# Setup requisite files
cp /opt/etc/fcron.conf /usr/local/etc/fcron.conf
chown root:fcron /usr/local/etc/fcron.conf
chmod 640 /usr/local/etc/fcron.conf

mkdir -p /var/spool/fcron
chown root:fcron /var/spool/fcron
chmod 644 /var/spool/fcron

# Remove pidfiles
rm -f /var/run/fcron.pid /var/run/fcron.fifo

# Start fcron
fcron -f --nosyslog &
