#!/usr/bin/env bash
set -euo pipefail

REMOTE="${BRIDGE_REMOTE:-root@89.116.191.85}"
REMOTE_BIND="${BRIDGE_REMOTE_BIND:-127.0.0.1}"
REMOTE_PORT="${BRIDGE_REMOTE_PORT:-15360}"
LOCAL_HOST="${BRIDGE_LOCAL_HOST:-127.0.0.1}"
LOCAL_PORT="${BRIDGE_LOCAL_PORT:-5000}"
RETRY_SECONDS="${BRIDGE_RETRY_SECONDS:-15}"
STATE_DIR="${BRIDGE_STATE_DIR:-/var/lib/tophand-bridge-tunnel}"
SSH_DIR="${STATE_DIR}/ssh"
KEY_PATH="${SSH_DIR}/bridge_ed25519"
KNOWN_HOSTS="${SSH_DIR}/known_hosts"

log() {
  printf '%s frigate-bridge-tunnel %s\n' "$(date -Is)" "$*"
}

write_key() {
  mkdir -p "${SSH_DIR}"
  chmod 700 "${SSH_DIR}"

  if [ -n "${BRIDGE_SSH_PRIVATE_KEY_B64:-}" ]; then
    printf '%s' "${BRIDGE_SSH_PRIVATE_KEY_B64}" | base64 -d > "${KEY_PATH}"
  elif [ -n "${BACKUP_SSH_PRIVATE_KEY_B64:-}" ]; then
    printf '%s' "${BACKUP_SSH_PRIVATE_KEY_B64}" | base64 -d > "${KEY_PATH}"
  elif [ -n "${BRIDGE_SSH_PRIVATE_KEY:-}" ]; then
    printf '%b' "${BRIDGE_SSH_PRIVATE_KEY}" > "${KEY_PATH}"
  elif [ -n "${BACKUP_SSH_PRIVATE_KEY:-}" ]; then
    printf '%b' "${BACKUP_SSH_PRIVATE_KEY}" > "${KEY_PATH}"
  else
    return 1
  fi

  chmod 600 "${KEY_PATH}"
  touch "${KNOWN_HOSTS}"
  chmod 600 "${KNOWN_HOSTS}"
}

while ! write_key; do
  log "waiting_for=BRIDGE_SSH_PRIVATE_KEY_B64_or_BACKUP_SSH_PRIVATE_KEY_B64 retry_seconds=${RETRY_SECONDS}"
  sleep "${RETRY_SECONDS}"
done

while true; do
  log "tunnel_start remote=${REMOTE} remote_forward=${REMOTE_BIND}:${REMOTE_PORT} local=${LOCAL_HOST}:${LOCAL_PORT}"
  ssh \
    -i "${KEY_PATH}" \
    -o UserKnownHostsFile="${KNOWN_HOSTS}" \
    -o StrictHostKeyChecking=accept-new \
    -o BatchMode=yes \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=2 \
    -N \
    -R "${REMOTE_BIND}:${REMOTE_PORT}:${LOCAL_HOST}:${LOCAL_PORT}" \
    "${REMOTE}" || true
  log "tunnel_exited retry_seconds=${RETRY_SECONDS}"
  sleep "${RETRY_SECONDS}"
done
