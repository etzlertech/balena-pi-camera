#!/usr/bin/env python3
"""Pi-side RanchView camera control relay.

The browser-facing RanchView MVP may run on a laptop that cannot route to the
camera-only switch. This relay runs on the Pi in the Frigate service, where the
camera credentials and camera network are already available.
"""

from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import requests
from requests.auth import HTTPDigestAuth


PORT = int(os.environ.get("EDGE_CONTROL_PORT", "8091"))

CAMERAS: dict[str, dict[str, Any]] = {
    "amcrest-mt2544ew-01": {
        "type": "amcrest_dahua_zoom",
        "host": "192.168.1.120",
        "channel": "0",
        "user_env": "FRIGATE_AMCREST_MT2544EW_01_USER",
        "password_env": "FRIGATE_AMCREST_MT2544EW_01_PASSWORD",
        "zoom_speed": 2,
        "pulse_ms": 1100,
        "homebase_pulse_ms": 2300,
    },
    "amcrest-mt2544ew-02": {
        "type": "amcrest_dahua_zoom",
        "host": "192.168.1.121",
        "channel": "0",
        "user_env": "FRIGATE_AMCREST_MT2544EW_02_USER",
        "password_env": "FRIGATE_AMCREST_MT2544EW_02_PASSWORD",
        "zoom_speed": 2,
        "pulse_ms": 1100,
        "homebase_pulse_ms": 2300,
    },
    "anpviz-ptz-06": {
        "type": "hikvision_isapi",
        "host": "192.168.1.175",
        "channel": "1",
        "user_env": "FRIGATE_ANPVIZ_PTZ_06_USER",
        "password_env": "FRIGATE_ANPVIZ_PTZ_06_PASSWORD",
        "speed": 45,
        "zoom_speed": 35,
    },
}


def credentials(camera: dict[str, Any]) -> tuple[str, str]:
    user = os.environ.get(str(camera.get("user_env", "")), "")
    password = os.environ.get(str(camera.get("password_env", "")), "")
    if not user or not password:
        raise ValueError("missing camera credentials")
    return user, password


def new_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


def ptz_vector(action: str, camera: dict[str, Any]) -> tuple[int, int, int] | None:
    speed = int(camera.get("speed", 45))
    zoom_speed = int(camera.get("zoom_speed", 35))
    vectors = {
        "left": (-speed, 0, 0),
        "right": (speed, 0, 0),
        "up": (0, speed, 0),
        "down": (0, -speed, 0),
        "zoom_in": (0, 0, zoom_speed),
        "zoom_out": (0, 0, -zoom_speed),
        "stop": (0, 0, 0),
    }
    return vectors.get(action)


def put_hikvision_ptz(session: requests.Session, camera: dict[str, Any], pan: int, tilt: int, zoom: int) -> None:
    user, password = credentials(camera)
    host = camera["host"]
    channel = camera.get("channel", "1")
    url = f"http://{host}/ISAPI/PTZCtrl/channels/{channel}/continuous"
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<PTZData version="2.0" xmlns="http://www.std-cgi.com/ver20/XMLSchema">
  <pan>{pan}</pan>
  <tilt>{tilt}</tilt>
  <zoom>{zoom}</zoom>
</PTZData>"""
    res = session.put(
        url,
        data=xml.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        auth=HTTPDigestAuth(user, password),
        timeout=3,
    )
    res.raise_for_status()


def put_amcrest_ptz(session: requests.Session, camera: dict[str, Any], verb: str, code: str, speed: int) -> None:
    user, password = credentials(camera)
    url = f"http://{camera['host']}/cgi-bin/ptz.cgi"
    params = {
        "action": verb,
        "channel": camera.get("channel", "0"),
        "code": code,
        "arg1": 0,
        "arg2": speed,
        "arg3": 0,
    }
    res = session.get(url, params=params, auth=HTTPDigestAuth(user, password), timeout=3)
    res.raise_for_status()


def send_hikvision_control(camera: dict[str, Any], action: str, duration_ms: int) -> dict[str, Any]:
    vector = ptz_vector(action, camera)
    if vector is None:
        return {"ok": False, "error": "unknown PTZ action"}

    duration = max(80, min(int(duration_ms), 800)) / 1000
    session = new_session()
    pan, tilt, zoom = vector
    put_hikvision_ptz(session, camera, pan, tilt, zoom)
    if action != "stop":
        time.sleep(duration)
        put_hikvision_ptz(session, camera, 0, 0, 0)
    return {"ok": True, "action": action, "relay": "pi-edge-control"}


def send_amcrest_zoom_control(camera: dict[str, Any], action: str, duration_ms: int) -> dict[str, Any]:
    codes = {
        "zoom_in": "ZoomTele",
        "zoom_out": "ZoomWide",
        "homebase": "ZoomWide",
    }
    session = new_session()
    speed = max(1, min(int(camera.get("zoom_speed", 2)), 8))
    if action == "stop":
        put_amcrest_ptz(session, camera, "stop", "ZoomTele", 0)
        put_amcrest_ptz(session, camera, "stop", "ZoomWide", 0)
        return {"ok": True, "action": action, "relay": "pi-edge-control"}
    if action not in codes:
        return {"ok": False, "error": "unknown zoom action"}

    configured_ms = duration_ms
    if action in {"zoom_in", "zoom_out"}:
        configured_ms = int(camera.get("pulse_ms", duration_ms))
    if action == "homebase":
        configured_ms = int(camera.get("homebase_pulse_ms", duration_ms))
    duration = max(80, min(int(configured_ms), 2400)) / 1000
    code = codes[action]
    put_amcrest_ptz(session, camera, "start", code, speed)
    time.sleep(duration)
    put_amcrest_ptz(session, camera, "stop", code, 0)
    return {
        "ok": True,
        "action": action,
        "command": code,
        "duration_ms": int(duration * 1000),
        "speed": speed,
        "relay": "pi-edge-control",
    }


def send_camera_control(camera_id: str, action: str, duration_ms: int) -> dict[str, Any]:
    camera = CAMERAS.get(camera_id)
    if not camera:
        return {"ok": False, "error": "unknown camera"}
    if camera.get("type") == "hikvision_isapi":
        return send_hikvision_control(camera, action, duration_ms)
    if camera.get("type") == "amcrest_dahua_zoom":
        return send_amcrest_zoom_control(camera, action, duration_ms)
    return {"ok": False, "error": "unsupported camera control"}


class Handler(BaseHTTPRequestHandler):
    server_version = "TopHandEdgeControl/0.1"

    def do_GET(self) -> None:
        if self.path == "/health":
            return self.json_response({"ok": True, "service": "edge-control", "cameras": sorted(CAMERAS)})
        return self.json_response({"ok": False, "error": "not found"}, status=404)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        prefix = "/api/control/"
        if not path.startswith(prefix):
            return self.json_response({"ok": False, "error": "not found"}, status=404)
        camera_id = path.removeprefix(prefix)
        body = self.read_json_body()
        action = str(body.get("action", "stop"))
        try:
            duration_ms = int(body.get("duration_ms", 220))
            result = send_camera_control(camera_id, action, duration_ms)
            return self.json_response(result, status=200 if result.get("ok") else 400)
        except Exception as exc:
            print(f"control_error camera={camera_id} action={action} error={type(exc).__name__}", flush=True)
            return self.json_response({"ok": False, "error": type(exc).__name__}, status=502)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def json_response(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        print("edge-control", self.address_string(), fmt % args, flush=True)


def main() -> None:
    print(f"TopHand edge control relay starting port={PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
