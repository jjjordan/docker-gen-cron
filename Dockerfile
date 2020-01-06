FROM alpine:3.11
ENTRYPOINT ["/sbin/tini", "/opt/bin/start.sh"]
ENV FCRON_VERSION=3.2.1 \
    DOCKER_VERSION=19.03.5 \
    DOCKER_GEN_VERSION=0.7.4
ADD opt /opt
RUN /bin/sh /opt/bin/install.sh
