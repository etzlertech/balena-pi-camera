const { Readable } = require("stream");

const BRIDGE_BASE = "http://89.116.191.85/threadgill-frigate";

const ALLOWED_PATHS = [
  /^\/api\/version$/,
  /^\/api\/events$/,
  /^\/api\/[^/]+\/latest\.jpg$/,
  /^\/api\/events\/[^/]+\/(clip\.mp4|snapshot\.jpg)$/,
];

module.exports = async function handler(req, res) {
  const rawPath = Array.isArray(req.query.path) ? req.query.path[0] : req.query.path;
  const path = typeof rawPath === "string" ? rawPath : "";
  if (!path || !path.startsWith("/api/") || path.includes("..") || !ALLOWED_PATHS.some((pattern) => pattern.test(path))) {
    res.statusCode = 403;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ error: "forbidden" }));
    return;
  }

  const upstreamUrl = new URL(`${BRIDGE_BASE}${path}`);
  for (const [key, value] of Object.entries(req.query)) {
    if (key === "path") continue;
    const values = Array.isArray(value) ? value : [value];
    for (const item of values) {
      if (item !== undefined) upstreamUrl.searchParams.append(key, item);
    }
  }

  const headers = {};
  if (req.headers.range) headers.Range = req.headers.range;

  try {
    const upstream = await fetch(upstreamUrl, { headers });
    res.statusCode = upstream.status;
    for (const header of ["content-type", "content-length", "content-range", "accept-ranges"]) {
      const value = upstream.headers.get(header);
      if (value) res.setHeader(header, value);
    }
    res.setHeader("Cache-Control", path.endsWith(".mp4") ? "private, max-age=5" : "no-store");
    res.setHeader("X-Threadgill-Live-Bridge", "true");

    if (req.method === "HEAD" || !upstream.body) {
      res.end();
      return;
    }
    Readable.fromWeb(upstream.body).pipe(res);
  } catch (error) {
    res.statusCode = 502;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ error: "bridge unavailable" }));
  }
};
