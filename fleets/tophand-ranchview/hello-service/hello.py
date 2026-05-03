import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


SITE_SLUG = os.environ.get("SITE_SLUG", "mark-threadgill")
DEVICE_NAME = os.environ.get(
    "BALENA_DEVICE_NAME_AT_INIT",
    os.environ.get("BALENA_DEVICE_NAME", "unknown-device"),
)
FLEET_NAME = os.environ.get(
    "BALENA_APP_NAME",
    os.environ.get("BALENA_APP_ID", "unknown-fleet"),
)
try:
    PORT = int(os.environ.get("HELLO_PORT", "8080"))
except ValueError:
    PORT = 8080
STARTED_AT = time.time()


def payload():
    return {
        "service": "tophand-ranchview-hello",
        "status": "ok",
        "site": SITE_SLUG,
        "device": DEVICE_NAME,
        "fleet": FLEET_NAME,
        "hostname": socket.gethostname(),
        "uptime_seconds": int(time.time() - STARTED_AT),
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(payload(), indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("http", self.address_string(), fmt % args, flush=True)


def heartbeat():
    while True:
        print(
            f"heartbeat site={SITE_SLUG} device={DEVICE_NAME} "
            f"fleet={FLEET_NAME} uptime_seconds={int(time.time() - STARTED_AT)}",
            flush=True,
        )
        time.sleep(60)


print("TopHand RanchView hello service starting", flush=True)
print(
    f"site={SITE_SLUG} device={DEVICE_NAME} fleet={FLEET_NAME} port={PORT}",
    flush=True,
)

threading.Thread(target=heartbeat, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
