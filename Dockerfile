FROM alpine:3.11
ENTRYPOINT ["/sbin/tini", "/opt/bin/start.sh"]
ADD opt /opt
RUN FCRON_VERSION=3.2.1 \
    DOCKER_GEN_VERSION=0.7.4 \
    /bin/sh /opt/bin/install.sh
