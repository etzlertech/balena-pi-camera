FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      openssh-client \
      rsync \
      sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY frigate-backup/start-frigate-backup.sh /usr/local/bin/start-frigate-backup.sh

RUN chmod +x /usr/local/bin/start-frigate-backup.sh

ENTRYPOINT ["/usr/local/bin/start-frigate-backup.sh"]
