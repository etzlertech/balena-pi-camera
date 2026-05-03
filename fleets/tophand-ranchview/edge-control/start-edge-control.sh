#!/usr/bin/env bash
set -euo pipefail

if command -v ip >/dev/null 2>&1 && [ "${TOPHAND_WIFI_INTERNET_ROUTE:-1}" = "1" ]; then
  WIFI_IF="${TOPHAND_WIFI_IF:-wlan0}"
  CAMERA_IF="${TOPHAND_CAMERA_IF:-eth0}"
  WIFI_GATEWAY="${TOPHAND_WIFI_GATEWAY:-192.168.1.1}"
  CAMERA_HOSTS="${TOPHAND_CAMERA_HOSTS:-192.168.1.120 192.168.1.121 192.168.1.122 192.168.1.175}"
  WIFI_IP="$(ip -4 addr show "$WIFI_IF" 2>/dev/null | awk '/inet / {print $2}' | cut -d/ -f1 | head -n 1 || true)"
  CAMERA_IP="$(ip -4 addr show "$CAMERA_IF" 2>/dev/null | awk '/inet / {print $2}' | cut -d/ -f1 | head -n 1 || true)"

  if [ -n "$WIFI_IP" ]; then
    ip route replace "${WIFI_GATEWAY}/32" dev "$WIFI_IF" src "$WIFI_IP" metric 20 || true
    ip route replace default via "$WIFI_GATEWAY" dev "$WIFI_IF" src "$WIFI_IP" metric 50 || true
    ip route del default via "$WIFI_GATEWAY" dev "$CAMERA_IF" 2>/dev/null || true
    ip route del default dev "$CAMERA_IF" 2>/dev/null || true
  else
    echo "warning=${WIFI_IF} has no IPv4 address; leaving default route unchanged"
  fi

  if [ -n "$CAMERA_IP" ]; then
    for host in $CAMERA_HOSTS; do
      ip route replace "${host}/32" dev "$CAMERA_IF" src "$CAMERA_IP" metric 10 || true
    done
  else
    echo "warning=${CAMERA_IF} has no IPv4 address; camera host routes not applied"
  fi
fi

echo "TopHand edge control starting"
exec python3 /opt/tophand/control-relay.py
