FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends iproute2 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir requests

WORKDIR /opt/tophand

COPY edge-control/control-relay.py /opt/tophand/control-relay.py
COPY edge-control/start-edge-control.sh /usr/local/bin/start-edge-control.sh

RUN chmod +x /usr/local/bin/start-edge-control.sh /opt/tophand/control-relay.py

ENTRYPOINT ["/usr/local/bin/start-edge-control.sh"]
