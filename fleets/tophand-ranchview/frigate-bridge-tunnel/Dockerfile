FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY frigate-bridge-tunnel/start-frigate-bridge-tunnel.sh /usr/local/bin/start-frigate-bridge-tunnel.sh

RUN chmod +x /usr/local/bin/start-frigate-bridge-tunnel.sh

ENTRYPOINT ["/usr/local/bin/start-frigate-bridge-tunnel.sh"]
