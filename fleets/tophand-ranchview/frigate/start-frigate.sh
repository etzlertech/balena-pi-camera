#!/usr/bin/env bash
set -euo pipefail

export FRIGATE_RTSP_USER="${FRIGATE_RTSP_USER:-admin}"
export FRIGATE_RTSP_PASSWORD="${FRIGATE_RTSP_PASSWORD:-unset}"
export FRIGATE_AMCREST_01_HOST="${FRIGATE_AMCREST_01_HOST:-192.168.1.121}"
export FRIGATE_AMCREST_02_HOST="${FRIGATE_AMCREST_02_HOST:-192.168.1.122}"
export FRIGATE_AMCREST_03_HOST="${FRIGATE_AMCREST_03_HOST:-192.168.1.175}"
export FRIGATE_AMCREST_01_SUBTYPE="${FRIGATE_AMCREST_01_SUBTYPE:-1}"
export FRIGATE_AMCREST_02_SUBTYPE="${FRIGATE_AMCREST_02_SUBTYPE:-1}"
export FRIGATE_AMCREST_03_SUBTYPE="${FRIGATE_AMCREST_03_SUBTYPE:-1}"

mkdir -p /config /media/frigate /tmp/cache
cp /opt/tophand/config.yml /config/config.yml

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

  echo "TopHand routes after camera/WiFi setup:"
  ip route show || true
fi

echo "TopHand Frigate starting"
echo "site=mark-threadgill camera=amcrest_01 host=${FRIGATE_AMCREST_01_HOST} subtype=${FRIGATE_AMCREST_01_SUBTYPE}"
echo "site=mark-threadgill camera=amcrest_02 host=${FRIGATE_AMCREST_02_HOST} subtype=${FRIGATE_AMCREST_02_SUBTYPE}"
echo "site=mark-threadgill camera=amcrest_03 host=${FRIGATE_AMCREST_03_HOST} subtype=${FRIGATE_AMCREST_03_SUBTYPE}"
if [ "${FRIGATE_RTSP_PASSWORD}" = "unset" ]; then
  echo "warning=FRIGATE_RTSP_PASSWORD is unset; camera auth will fail until the Balena env var is configured"
fi

exec /init
