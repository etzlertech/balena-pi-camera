#!/usr/bin/env bash
set -euo pipefail

SOURCE="${BACKUP_SOURCE:-/media/frigate}"
DEST="${BACKUP_DEST:-travis@100.120.124.113:/data/archive/threadgill/frigate-recordings/media/}"
MANIFEST_DEST="${BACKUP_MANIFEST_DEST:-travis@100.120.124.113:/data/archive/threadgill/frigate-recordings/manifests/}"
INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-300}"
STATE_DIR="${BACKUP_STATE_DIR:-/var/lib/tophand-backup}"
SSH_DIR="${STATE_DIR}/ssh"
KEY_PATH="${SSH_DIR}/backup_ed25519"
KNOWN_HOSTS="${SSH_DIR}/known_hosts"
HOST_ID="${BALENA_DEVICE_UUID:-${HOSTNAME:-tophand-ranchview}}"

log() {
  printf '%s frigate-backup %s\n' "$(date -Is)" "$*"
}

sleep_waiting() {
  log "$1"
  sleep "${BACKUP_RETRY_SECONDS:-60}"
}

write_key() {
  mkdir -p "${SSH_DIR}"
  chmod 700 "${SSH_DIR}"

  if [ -n "${BACKUP_SSH_PRIVATE_KEY_B64:-}" ]; then
    printf '%s' "${BACKUP_SSH_PRIVATE_KEY_B64}" | base64 -d > "${KEY_PATH}"
  elif [ -n "${BACKUP_SSH_PRIVATE_KEY:-}" ]; then
    printf '%b' "${BACKUP_SSH_PRIVATE_KEY}" > "${KEY_PATH}"
  else
    return 1
  fi

  chmod 600 "${KEY_PATH}"
  touch "${KNOWN_HOSTS}"
  chmod 600 "${KNOWN_HOSTS}"
}

ssh_args() {
  printf '%s\n' \
    -i "${KEY_PATH}" \
    -o UserKnownHostsFile="${KNOWN_HOSTS}" \
    -o StrictHostKeyChecking=accept-new \
    -o BatchMode=yes \
    -o ConnectTimeout=20 \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=2
}

rsync_ssh() {
  local args
  args="$(ssh_args | tr '\n' ' ')"
  printf 'ssh %s' "${args}"
}

backup_sqlite_db() {
  local db_path="${SOURCE%/}/frigate.db"
  local db_copy="${STATE_DIR}/frigate.db"
  if [ ! -s "${db_path}" ]; then
    return 0
  fi

  if sqlite3 "${db_path}" ".backup '${db_copy}.tmp'"; then
    mv "${db_copy}.tmp" "${db_copy}"
  else
    rm -f "${db_copy}.tmp"
    log "warning=sqlite_backup_failed source=${db_path}"
  fi
}

write_manifest() {
  local manifest="${STATE_DIR}/latest-${HOST_ID}.json"
  local timestamp
  timestamp="$(date -Is)"
  cat > "${manifest}" <<EOF
{
  "site": "mark-threadgill",
  "service": "frigate-backup",
  "host_id": "${HOST_ID}",
  "timestamp": "${timestamp}",
  "source": "${SOURCE}",
  "destination": "${DEST}"
}
EOF
}

sync_once() {
  if [ ! -d "${SOURCE}" ]; then
    log "warning=source_missing source=${SOURCE}"
    return 1
  fi

  backup_sqlite_db

  log "sync_start source=${SOURCE} dest=${DEST}"
  rsync -a \
    --human-readable \
    --info=stats2 \
    --partial \
    --append-verify \
    --mkpath \
    --protect-args \
    --timeout=120 \
    --contimeout=30 \
    --exclude '/frigate.db' \
    --exclude '/cache/' \
    --exclude '/exports/tmp/' \
    -e "$(rsync_ssh)" \
    "${SOURCE%/}/" \
    "${DEST}"

  if [ -s "${STATE_DIR}/frigate.db" ]; then
    rsync -a \
      --mkpath \
      --protect-args \
      -e "$(rsync_ssh)" \
      "${STATE_DIR}/frigate.db" \
      "${DEST%/}/frigate.db"
  fi

  write_manifest
  rsync -a \
    --mkpath \
    --protect-args \
    -e "$(rsync_ssh)" \
    "${STATE_DIR}/latest-${HOST_ID}.json" \
    "${MANIFEST_DEST%/}/latest-${HOST_ID}.json"

  log "sync_complete dest=${DEST}"
}

main() {
  log "starting interval_seconds=${INTERVAL_SECONDS} source=${SOURCE} dest=${DEST}"

  while ! write_key; do
    sleep_waiting "waiting_for=BACKUP_SSH_PRIVATE_KEY_B64"
  done

  while true; do
    sync_once || log "sync_failed retry_seconds=${INTERVAL_SECONDS}"
    sleep "${INTERVAL_SECONDS}"
  done
}

main
