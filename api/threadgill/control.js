const CONTROL_BASE = "http://89.116.191.85/threadgill-control";

const ALLOWED_CAMERAS = new Set([
  "amcrest-mt2544ew-01",
  "amcrest-mt2544ew-02",
  "anpviz-ptz-06",
]);

const ALLOWED_ACTIONS = new Set([
  "up",
  "down",
  "left",
  "right",
  "zoom_in",
  "zoom_out",
  "homebase",
  "stop",
]);

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      if (!chunks.length) return resolve({});
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf8")));
      } catch (error) {
        reject(error);
      }
    });
    req.on("error", reject);
  });
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.statusCode = 405;
    res.setHeader("Allow", "POST");
    res.end("method not allowed");
    return;
  }

  const camera = Array.isArray(req.query.camera) ? req.query.camera[0] : req.query.camera;
  if (!ALLOWED_CAMERAS.has(camera)) {
    res.statusCode = 403;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ ok: false, error: "camera not allowed" }));
    return;
  }

  let body;
  try {
    body = await readBody(req);
  } catch {
    res.statusCode = 400;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ ok: false, error: "invalid json" }));
    return;
  }

  const action = String(body.action || "stop");
  if (!ALLOWED_ACTIONS.has(action)) {
    res.statusCode = 400;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ ok: false, error: "action not allowed" }));
    return;
  }

  const duration = Math.max(80, Math.min(Number(body.duration_ms || 220), 2400));
  try {
    const upstream = await fetch(`${CONTROL_BASE}/api/control/${encodeURIComponent(camera)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, duration_ms: duration }),
    });
    const text = await upstream.text();
    res.statusCode = upstream.status;
    res.setHeader("Content-Type", upstream.headers.get("content-type") || "application/json");
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("X-Threadgill-Control-Bridge", "true");
    res.end(text);
  } catch {
    res.statusCode = 502;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ ok: false, error: "control bridge unavailable" }));
  }
};
