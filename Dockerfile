FROM debian:10.2-slim
ENTRYPOINT ["/usr/bin/tini", "/opt/bin/start.sh"]
ENV FCRON_VERSION=3.2.1 \
    DOCKER_VERSION=18.06.3-ce \
    DOCKER_GEN_VERSION=0.7.4
ADD opt /opt
RUN /bin/sh /opt/bin/install.sh
