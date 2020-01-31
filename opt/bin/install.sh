#!/bin/sh

# Install prerequisites
echo ==== Installing prerequisite packages
BUILD_PACKAGES="build-base wget perl shadow"
RUN_PACKAGES="tini ca-certificates tzdata python3 msmtp"
apk update
apk add $BUILD_PACKAGES $RUN_PACKAGES || exit $?

# Compile runjob
echo ==== Compiling runjob wrapper
cd /opt/bin
gcc -o runjob runjob.c -Wall -Os || exit $?
chmod u+s runjob || exit $?

cd /tmp

# Install fcron
echo ==== Installing fcron $FCRON_VERSION
FCRON_TGZ=fcron-$FCRON_VERSION.src.tar.gz
test -f $FCRON_TGZ || wget http://fcron.free.fr/archives/$FCRON_TGZ || exit $?
tar xf $FCRON_TGZ || exit $?
cd fcron-$FCRON_VERSION
./configure --with-sendmail=/usr/bin/msmtp --with-editor=/bin/ed || exit $?
make -j || exit $?
useradd -rU -u 122 fcron || exit $?
make install || exit $?
cd /tmp

# Install docker-gen
ARCH=$(uname -m)
case $ARCH in
	x86_64)
		ARCH=amd64
		break
		;;
esac

echo ==== Installing docker-gen $DOCKER_VERSION - arch $ARCH
DOCKER_GEN_TGZ=docker-gen-linux-$ARCH-$DOCKER_GEN_VERSION.tar.gz
test -f $DOCKER_GEN_TGZ || wget https://github.com/jwilder/docker-gen/releases/download/$DOCKER_GEN_VERSION/$DOCKER_GEN_TGZ || exit $?
tar xf $DOCKER_GEN_TGZ || exit $?
mv docker-gen /usr/local/bin || exit $?

echo ==== Installing python requirements
pip3 install --no-cache-dir -r /opt/lib/requirements.txt || exit $?

# Set up permissions/dirs
chmod 755 /opt/bin/*.sh /opt/lib/reload.py /opt/lib/runjob.py /opt/lib/waitsig.py
mkdir -p /var/etc

# Clean up
apk del $BUILD_PACKAGES
rm -rf /tmp/* /var/tmp/*

exit 0
