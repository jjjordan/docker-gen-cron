#!/bin/sh

# Install prerequisites
echo ==== Installing prequisite packages
BUILD_PACKAGES="build-essential wget"
RUN_PACKAGES="tini ca-certificates python3 msmtp elvis-tiny"
apt-get update -y -qq || exit $?
apt-get install -y -qq $BUILD_PACKAGES $RUN_PACKAGES --no-install-recommends || exit $?

cd /tmp

# Install fcron
echo ==== Installing fcron $FCRON_VERSION
FCRON_TGZ=fcron-$FCRON_VERSION.src.tar.gz
test -f $FCRON_TGZ || wget http://fcron.free.fr/archives/$FCRON_TGZ || exit $?
tar xf $FCRON_TGZ || exit $?
cd fcron-$FCRON_VERSION
./configure --with-sendmail=/usr/bin/msmtp || exit $?
make || exit $?
make install || exit $?
cd /tmp

# Install docker client
echo ==== Installing docker client $DOCKER_VERSION
DOCKER_TGZ=docker-$DOCKER_VERSION.tgz
test -f $DOCKER_TGZ || wget https://download.docker.com/linux/static/stable/$(uname -m)/$DOCKER_TGZ || exit $?
tar xf $DOCKER_TGZ docker/docker || exit $?
mv docker/docker /usr/local/bin/docker || exit $?

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

# Clean up
chmod 755 /opt/bin/*
chmod 755 /opt/lib/generate.py /opt/lib/siglisten.py /opt/lib/runjob.py

apt-get -y -qq purge $BUILD_PACKAGES
apt-get -y -qq autoremove
apt-get -y -qq clean
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
exit 0
