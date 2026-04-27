#!/usr/bin/env python3
"""Small browser UI for creating Pastucha Hay golden labels.

This is intentionally dependency-light: stdlib HTTP server plus the existing
Supabase helper from `tophand_branding_worker.py`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    import tophand_branding_worker as branding
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("Run this from a checkout containing tools/tophand_branding_worker.py") from exc


CAMERA_ID = "FLEX-M-MGE4"
CAMERA_TITLE = "Pastucha Hay"
DEST_BUCKET = branding.DEST_BUCKET
DEFAULT_DATA_DIR = Path("/home/travis/tophand-instances/sdco/research/pastucha-hay")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pastucha Hay golden-label UI")
    parser.add_argument("--env", type=Path, default=Path("/home/travis/tophand-instances/sdco/.secrets/dtzay-supabase.env"))
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8771)
    parser.add_argument("--manifest-path", default="manifest.json")
    parser.add_argument("--source-bucket", default=branding.SOURCE_BUCKET)
    parser.add_argument("--source-queue", type=Path)
    return parser.parse_args()


def parse_time(value: str | None) -> dt.datetime:
    if not value:
        return dt.datetime.min.replace(tzinfo=dt.UTC)
    cleaned = value.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(cleaned)
    except ValueError:
        return dt.datetime.min.replace(tzinfo=dt.UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


class LabelStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.latest_path = data_dir / "golden_labels.latest.json"
        self.jsonl_path = data_dir / "golden_labels.jsonl"
        self.latest: dict[str, Any] = self.canonicalize(read_json(self.latest_path, {}))

    @staticmethod
    def label_key(payload: dict[str, Any]) -> str:
        return str(payload.get("source_path") or payload.get("path") or "")

    @staticmethod
    def is_newer(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
        candidate_time = parse_time(candidate.get("updated_at") or candidate.get("captured_at"))
        current_time = parse_time(current.get("updated_at") or current.get("captured_at"))
        return candidate_time >= current_time

    def canonicalize(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        canonical: dict[str, Any] = {}
        changed = False
        for fallback_key, value in payload.items():
            if not isinstance(value, dict):
                continue
            row = dict(value)
            key = self.label_key(row) or str(fallback_key)
            if key != fallback_key:
                changed = True
            existing = canonical.get(key)
            if existing is None or self.is_newer(row, existing):
                canonical[key] = row
        if changed:
            write_json(self.latest_path, canonical)
        return canonical

    def get(self, *image_paths: str | None) -> dict[str, Any] | None:
        for image_path in image_paths:
            if not image_path:
                continue
            value = self.latest.get(image_path)
            if isinstance(value, dict):
                return value
        return None

    def upsert(self, payload: dict[str, Any]) -> dict[str, Any]:
        image_path = self.label_key(payload)
        if not image_path:
            raise ValueError("Missing image path")
        now = dt.datetime.now(dt.UTC).isoformat()
        payload["updated_at"] = now
        payload.setdefault("schema_version", "pastucha_hay_label_v3")
        self.latest[image_path] = payload
        write_json(self.latest_path, self.latest)
        append_jsonl(self.jsonl_path, payload)
        return payload


class ImageIndex:
    def __init__(
        self,
        client: branding.SupabaseRest,
        manifest_path: str,
        source_bucket: str,
        source_queue_path: Path | None,
    ) -> None:
        self.client = client
        self.manifest_path = manifest_path
        self.source_bucket = source_bucket
        self.source_queue_path = source_queue_path
        self.images: list[dict[str, Any]] = []
        self.reload()

    def reload(self) -> None:
        manifest = self.client.download_json_optional(DEST_BUCKET, self.manifest_path)
        if not manifest:
            raise RuntimeError(f"Could not load {DEST_BUCKET}/{self.manifest_path}")
        images = []
        for item in manifest.get("images", []):
            if item.get("device") != CAMERA_ID:
                continue
            row = dict(item)
            row["public_url"] = self.client.public_url(DEST_BUCKET, row["path"])
            row["sort_time"] = parse_time(row.get("captured_at")).isoformat()
            row["image_mode"] = "branded"
            images.append(row)

        seen_sources = {row.get("source_path") or row.get("path") for row in images}
        if self.source_queue_path and self.source_queue_path.exists():
            queue = read_json(self.source_queue_path, {})
            for item in queue.get("images", []):
                if item.get("device") != CAMERA_ID:
                    continue
                if not item.get("overlay_verified"):
                    continue
                if not item.get("captured_at"):
                    continue
                if not str(item.get("capture_time_source") or "").startswith("image_overlay_"):
                    continue
                source_path = item.get("source_path") or item.get("path")
                if not source_path or source_path in seen_sources:
                    continue
                row = dict(item)
                row["path"] = source_path
                row["source_path"] = source_path
                row["public_url"] = self.client.public_url(self.source_bucket, source_path)
                row["sort_time"] = parse_time(row.get("captured_at")).isoformat()
                row["camera_title"] = CAMERA_TITLE
                row["image_mode"] = "source"
                images.append(row)
                seen_sources.add(source_path)
        images.sort(key=lambda row: parse_time(row.get("captured_at")), reverse=True)
        self.images = images

    def query(self, params: dict[str, list[str]], labels: LabelStore) -> list[dict[str, Any]]:
        start = (params.get("start") or [""])[0]
        end = (params.get("end") or [""])[0]
        limit = int((params.get("limit") or ["300"])[0] or 300)
        unlabeled_only = (params.get("unlabeled") or ["0"])[0] in {"1", "true", "yes"}

        start_dt = dt.datetime.fromisoformat(start).replace(tzinfo=branding.CAPTURE_TZ) if start else None
        end_dt = dt.datetime.fromisoformat(end).replace(hour=23, minute=59, second=59, tzinfo=branding.CAPTURE_TZ) if end else None

        rows = []
        for image in self.images:
            captured = parse_time(image.get("captured_at"))
            if start_dt and captured < start_dt:
                continue
            if end_dt and captured > end_dt:
                continue
            existing = labels.get(image.get("source_path"), image.get("path"))
            if unlabeled_only and existing:
                continue
            row = dict(image)
            row["label"] = existing
            rows.append(row)
            if len(rows) >= limit:
                break
        return rows


def html_page() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pastucha Hay Golden Labels</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #151515;
      --panel: #242424;
      --panel-2: #303030;
      --text: #f2f2f2;
      --muted: #aaa;
      --line: #444;
      --gold: #d6b56d;
      --green: #49b35a;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 16px 20px;
      border-bottom: 1px solid var(--line);
      background: #111;
      position: sticky;
      top: 0;
      z-index: 5;
    }
    h1 { font-size: 20px; margin: 0; }
    .sub { color: var(--gold); font-size: 12px; font-weight: 700; letter-spacing: .1em; }
    .filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: end; }
    label { display: grid; gap: 4px; color: var(--muted); font-size: 12px; }
    input, select, textarea, button {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel-2);
      color: var(--text);
      padding: 9px 10px;
      font: inherit;
    }
    button { cursor: pointer; font-weight: 700; }
    button.primary { background: var(--green); border-color: var(--green); color: white; }
    main {
      display: grid;
      grid-template-columns: 300px minmax(420px, 1fr) 440px;
      min-height: calc(100vh - 74px);
    }
    aside, section { min-width: 0; }
    .list {
      border-right: 1px solid var(--line);
      overflow: auto;
      max-height: calc(100vh - 74px);
    }
    .item {
      display: grid;
      grid-template-columns: 72px 1fr;
      gap: 10px;
      padding: 10px;
      border-bottom: 1px solid #333;
      cursor: pointer;
    }
    .item.active { background: #333; outline: 1px solid var(--gold); }
    .item img { width: 72px; height: 54px; object-fit: cover; border-radius: 4px; }
    .item strong { display: block; font-size: 13px; }
    .item span { display: block; color: var(--muted); font-size: 12px; margin-top: 3px; }
    .badge { color: var(--gold); font-weight: 700; }
    .viewer {
      padding: 18px;
      display: grid;
      align-content: start;
      gap: 12px;
    }
    .viewer img {
      width: 100%;
      max-height: 76vh;
      object-fit: contain;
      background: #050505;
      border-radius: 8px;
    }
    .meta { color: var(--muted); display: flex; gap: 10px; flex-wrap: wrap; }
    .form {
      border-left: 1px solid var(--line);
      padding: 18px;
      overflow: auto;
      max-height: calc(100vh - 74px);
      background: #1d1d1d;
    }
    .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
    .grid4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
    .bale-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
    .bale-slot {
      background: var(--panel);
      border: 1px solid #383838;
      border-radius: 8px;
      padding: 10px;
      display: grid;
      gap: 8px;
    }
    .bale-slot h4 {
      margin: 0;
      color: var(--gold);
      font-size: 13px;
    }
    .bale-slot .slot-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    .bale-slot .slot-title label {
      display: flex;
      grid-auto-flow: column;
      align-items: center;
      gap: 6px;
      color: var(--text);
      font-size: 12px;
    }
    .checks { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
    .checks label {
      display: flex;
      align-items: center;
      gap: 6px;
      background: var(--panel);
      padding: 8px 9px;
      border-radius: 6px;
    }
    input[readonly] { opacity: .72; }
    input:disabled, select:disabled, textarea:disabled { opacity: .48; }
    .actions { display: flex; gap: 10px; margin-top: 14px; }
    .status { color: var(--gold); min-height: 20px; margin-top: 10px; }
    @media (max-width: 1100px) {
      main { grid-template-columns: 1fr; }
      .list, .form { max-height: none; border: 0; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Pastucha Hay Golden Labels</h1>
      <div class="sub">FLEX-M-MGE4 ROUND BALE RESEARCH</div>
    </div>
    <div class="filters">
      <label>Start <input id="start" type="date"></label>
      <label>End <input id="end" type="date"></label>
      <label>Limit <input id="limit" type="number" value="300" min="1" max="1000"></label>
      <label>Range
        <select id="range_preset">
          <option value="">Custom / recent</option>
          <option value="2026-01-17:2026-04-26">All history</option>
          <option value="2026-01-17:2026-01-22">Jan 17-22</option>
          <option value="2026-01-23:2026-01-30">Jan 23-30</option>
          <option value="2026-02-15:2026-02-21">Feb 15-21</option>
          <option value="2026-03-04:2026-03-12">Mar 4-12</option>
        </select>
      </label>
      <label><span>&nbsp;</span><select id="unlabeled"><option value="0">All</option><option value="1">Unlabeled only</option></select></label>
      <button id="load" class="primary">Load</button>
    </div>
  </header>
  <main>
    <aside class="list" id="list"></aside>
    <section class="viewer">
      <img id="image" alt="">
      <div class="meta" id="meta"></div>
      <div class="actions">
        <button id="prev">Previous</button>
        <button id="next">Next</button>
      </div>
    </section>
    <section class="form">
      <h2 style="margin-top:0">Your Interpretation</h2>
      <div class="checks">
        <label><input id="no_bales_confirmed" type="checkbox"> No bales confirmed</label>
      </div>
      <div class="grid2">
        <label>Round bales visible <input id="round_bales_visible" type="number" min="0" max="10"></label>
        <label>Bale equivalents remaining <input id="bale_equivalents_remaining" type="number" min="0" max="10" step="0.1"></label>
        <label>Estimated hay days remaining <input id="hay_days_remaining" type="number" min="0" max="30" step="0.5"></label>
        <label>Total cattle <input id="cattle_count" type="number" min="0" max="200" readonly></label>
      </div>
      <h3>Animals</h3>
      <div class="grid3">
        <label>Cows <input id="cow_count" type="number" min="0" max="200"></label>
        <label>Calves <input id="calf_count" type="number" min="0" max="200"></label>
        <label>Bulls <input id="bull_count" type="number" min="0" max="20"></label>
      </div>
      <div class="checks">
        <label><input id="cattle_present" type="checkbox"> Cattle present</label>
      </div>
      <h3>Bale Slots</h3>
      <div class="bale-grid">
        <div class="bale-slot">
          <div class="slot-title">
            <h4>Bale 1</h4>
            <label><input id="bale_1_present" type="checkbox"> Present</label>
          </div>
          <label>Position
            <select id="bale_1_location">
              <option value="left">Left</option>
              <option value="middle">Middle</option>
              <option value="right">Right</option>
              <option value="far_left">Far left</option>
              <option value="far_right">Far right</option>
              <option value="background">Background</option>
              <option value="foreground">Foreground</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Remaining % <input id="bale_1_remaining_percent" type="number" min="0" max="100"></label>
          <label>Condition
            <select id="bale_1_condition">
              <option value="unknown">Unknown</option>
              <option value="new">New</option>
              <option value="mostly_full">Mostly full</option>
              <option value="half">Half</option>
              <option value="low">Low</option>
              <option value="collapsed">Collapsed</option>
              <option value="scattered">Mostly scattered</option>
              <option value="gone">Gone</option>
            </select>
          </label>
          <label>Color / quality
            <select id="bale_1_color_quality">
              <option value="normal">Normal</option>
              <option value="bright_fresh">Bright / fresh</option>
              <option value="dark_weathered">Dark / weathered</option>
              <option value="mixed">Mixed</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <div class="checks">
            <label><input id="bale_1_hay_ring_visible" type="checkbox"> Hay ring</label>
            <label><input id="bale_1_scatter_present" type="checkbox"> Scatter</label>
          </div>
          <label>Scatter level
            <select id="bale_1_scatter_level">
              <option value="none">None</option>
              <option value="trace">Trace</option>
              <option value="light">Light</option>
              <option value="moderate">Moderate</option>
              <option value="heavy">Heavy</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Scatter bale equivalent <input id="bale_1_scatter_bale_equivalent" type="number" min="0" max="1" step="0.01"></label>
          <label>Slot visibility
            <select id="bale_1_visibility">
              <option value="clear">Clear</option>
              <option value="partly_occluded">Partly occluded</option>
              <option value="mostly_occluded">Mostly occluded</option>
              <option value="night_uncertain">Night uncertain</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Level confidence
            <select id="bale_1_level_confidence">
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Occlusion amount
            <select id="bale_1_occlusion_level">
              <option value="none">None</option>
              <option value="light">Light</option>
              <option value="moderate">Moderate</option>
              <option value="heavy">Heavy</option>
              <option value="blocked">Blocked</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Occluded by
            <select id="bale_1_occluded_by">
              <option value="none">None</option>
              <option value="cow">Cow</option>
              <option value="cattle_group">Cattle group</option>
              <option value="hay_ring">Hay ring</option>
              <option value="brush">Brush</option>
              <option value="shadow">Shadow</option>
              <option value="night">Night</option>
              <option value="terrain">Terrain / rise</option>
              <option value="equipment">Equipment</option>
              <option value="other">Other</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Occlusion note <input id="bale_1_occlusion_note" type="text" maxlength="140"></label>
        </div>
        <div class="bale-slot">
          <div class="slot-title">
            <h4>Bale 2</h4>
            <label><input id="bale_2_present" type="checkbox"> Present</label>
          </div>
          <label>Position
            <select id="bale_2_location">
              <option value="left">Left</option>
              <option value="middle">Middle</option>
              <option value="right">Right</option>
              <option value="far_left">Far left</option>
              <option value="far_right">Far right</option>
              <option value="background">Background</option>
              <option value="foreground">Foreground</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Remaining % <input id="bale_2_remaining_percent" type="number" min="0" max="100"></label>
          <label>Condition
            <select id="bale_2_condition">
              <option value="unknown">Unknown</option>
              <option value="new">New</option>
              <option value="mostly_full">Mostly full</option>
              <option value="half">Half</option>
              <option value="low">Low</option>
              <option value="collapsed">Collapsed</option>
              <option value="scattered">Mostly scattered</option>
              <option value="gone">Gone</option>
            </select>
          </label>
          <label>Color / quality
            <select id="bale_2_color_quality">
              <option value="normal">Normal</option>
              <option value="bright_fresh">Bright / fresh</option>
              <option value="dark_weathered">Dark / weathered</option>
              <option value="mixed">Mixed</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <div class="checks">
            <label><input id="bale_2_hay_ring_visible" type="checkbox"> Hay ring</label>
            <label><input id="bale_2_scatter_present" type="checkbox"> Scatter</label>
          </div>
          <label>Scatter level
            <select id="bale_2_scatter_level">
              <option value="none">None</option>
              <option value="trace">Trace</option>
              <option value="light">Light</option>
              <option value="moderate">Moderate</option>
              <option value="heavy">Heavy</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Scatter bale equivalent <input id="bale_2_scatter_bale_equivalent" type="number" min="0" max="1" step="0.01"></label>
          <label>Slot visibility
            <select id="bale_2_visibility">
              <option value="clear">Clear</option>
              <option value="partly_occluded">Partly occluded</option>
              <option value="mostly_occluded">Mostly occluded</option>
              <option value="night_uncertain">Night uncertain</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Level confidence
            <select id="bale_2_level_confidence">
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Occlusion amount
            <select id="bale_2_occlusion_level">
              <option value="none">None</option>
              <option value="light">Light</option>
              <option value="moderate">Moderate</option>
              <option value="heavy">Heavy</option>
              <option value="blocked">Blocked</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Occluded by
            <select id="bale_2_occluded_by">
              <option value="none">None</option>
              <option value="cow">Cow</option>
              <option value="cattle_group">Cattle group</option>
              <option value="hay_ring">Hay ring</option>
              <option value="brush">Brush</option>
              <option value="shadow">Shadow</option>
              <option value="night">Night</option>
              <option value="terrain">Terrain / rise</option>
              <option value="equipment">Equipment</option>
              <option value="other">Other</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Occlusion note <input id="bale_2_occlusion_note" type="text" maxlength="140"></label>
        </div>
        <div class="bale-slot">
          <div class="slot-title">
            <h4>Bale 3</h4>
            <label><input id="bale_3_present" type="checkbox"> Present</label>
          </div>
          <label>Position
            <select id="bale_3_location">
              <option value="left">Left</option>
              <option value="middle">Middle</option>
              <option value="right">Right</option>
              <option value="far_left">Far left</option>
              <option value="far_right">Far right</option>
              <option value="background">Background</option>
              <option value="foreground">Foreground</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Remaining % <input id="bale_3_remaining_percent" type="number" min="0" max="100"></label>
          <label>Condition
            <select id="bale_3_condition">
              <option value="unknown">Unknown</option>
              <option value="new">New</option>
              <option value="mostly_full">Mostly full</option>
              <option value="half">Half</option>
              <option value="low">Low</option>
              <option value="collapsed">Collapsed</option>
              <option value="scattered">Mostly scattered</option>
              <option value="gone">Gone</option>
            </select>
          </label>
          <label>Color / quality
            <select id="bale_3_color_quality">
              <option value="normal">Normal</option>
              <option value="bright_fresh">Bright / fresh</option>
              <option value="dark_weathered">Dark / weathered</option>
              <option value="mixed">Mixed</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <div class="checks">
            <label><input id="bale_3_hay_ring_visible" type="checkbox"> Hay ring</label>
            <label><input id="bale_3_scatter_present" type="checkbox"> Scatter</label>
          </div>
          <label>Scatter level
            <select id="bale_3_scatter_level">
              <option value="none">None</option>
              <option value="trace">Trace</option>
              <option value="light">Light</option>
              <option value="moderate">Moderate</option>
              <option value="heavy">Heavy</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Scatter bale equivalent <input id="bale_3_scatter_bale_equivalent" type="number" min="0" max="1" step="0.01"></label>
          <label>Slot visibility
            <select id="bale_3_visibility">
              <option value="clear">Clear</option>
              <option value="partly_occluded">Partly occluded</option>
              <option value="mostly_occluded">Mostly occluded</option>
              <option value="night_uncertain">Night uncertain</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Level confidence
            <select id="bale_3_level_confidence">
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Occlusion amount
            <select id="bale_3_occlusion_level">
              <option value="none">None</option>
              <option value="light">Light</option>
              <option value="moderate">Moderate</option>
              <option value="heavy">Heavy</option>
              <option value="blocked">Blocked</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Occluded by
            <select id="bale_3_occluded_by">
              <option value="none">None</option>
              <option value="cow">Cow</option>
              <option value="cattle_group">Cattle group</option>
              <option value="hay_ring">Hay ring</option>
              <option value="brush">Brush</option>
              <option value="shadow">Shadow</option>
              <option value="night">Night</option>
              <option value="terrain">Terrain / rise</option>
              <option value="equipment">Equipment</option>
              <option value="other">Other</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Occlusion note <input id="bale_3_occlusion_note" type="text" maxlength="140"></label>
        </div>
        <div class="bale-slot">
          <div class="slot-title">
            <h4>Bale 4</h4>
            <label><input id="bale_4_present" type="checkbox"> Present</label>
          </div>
          <label>Position
            <select id="bale_4_location">
              <option value="unknown">Unknown</option>
              <option value="left">Left</option>
              <option value="middle">Middle</option>
              <option value="right">Right</option>
              <option value="far_left">Far left</option>
              <option value="far_right">Far right</option>
              <option value="background">Background</option>
              <option value="foreground">Foreground</option>
              <option value="custom">Custom</option>
            </select>
          </label>
          <label>Remaining % <input id="bale_4_remaining_percent" type="number" min="0" max="100"></label>
          <label>Condition
            <select id="bale_4_condition">
              <option value="unknown">Unknown</option>
              <option value="new">New</option>
              <option value="mostly_full">Mostly full</option>
              <option value="half">Half</option>
              <option value="low">Low</option>
              <option value="collapsed">Collapsed</option>
              <option value="scattered">Mostly scattered</option>
              <option value="gone">Gone</option>
            </select>
          </label>
          <label>Color / quality
            <select id="bale_4_color_quality">
              <option value="normal">Normal</option>
              <option value="bright_fresh">Bright / fresh</option>
              <option value="dark_weathered">Dark / weathered</option>
              <option value="mixed">Mixed</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <div class="checks">
            <label><input id="bale_4_hay_ring_visible" type="checkbox"> Hay ring</label>
            <label><input id="bale_4_scatter_present" type="checkbox"> Scatter</label>
          </div>
          <label>Scatter level
            <select id="bale_4_scatter_level">
              <option value="none">None</option>
              <option value="trace">Trace</option>
              <option value="light">Light</option>
              <option value="moderate">Moderate</option>
              <option value="heavy">Heavy</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Scatter bale equivalent <input id="bale_4_scatter_bale_equivalent" type="number" min="0" max="1" step="0.01"></label>
          <label>Slot visibility
            <select id="bale_4_visibility">
              <option value="clear">Clear</option>
              <option value="partly_occluded">Partly occluded</option>
              <option value="mostly_occluded">Mostly occluded</option>
              <option value="night_uncertain">Night uncertain</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Level confidence
            <select id="bale_4_level_confidence">
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Occlusion amount
            <select id="bale_4_occlusion_level">
              <option value="none">None</option>
              <option value="light">Light</option>
              <option value="moderate">Moderate</option>
              <option value="heavy">Heavy</option>
              <option value="blocked">Blocked</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Occluded by
            <select id="bale_4_occluded_by">
              <option value="none">None</option>
              <option value="cow">Cow</option>
              <option value="cattle_group">Cattle group</option>
              <option value="hay_ring">Hay ring</option>
              <option value="brush">Brush</option>
              <option value="shadow">Shadow</option>
              <option value="night">Night</option>
              <option value="terrain">Terrain / rise</option>
              <option value="equipment">Equipment</option>
              <option value="other">Other</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>Occlusion note <input id="bale_4_occlusion_note" type="text" maxlength="140"></label>
          <label>Position note <input id="bale_4_position_note" type="text" maxlength="120"></label>
        </div>
      </div>
      <h3>Scene Scatter / Residue</h3>
      <div class="checks">
        <label><input id="hay_scatter_present" type="checkbox"> Edible scatter visible</label>
      </div>
      <div class="grid2" style="margin-top:10px">
        <label>Scatter level
          <select id="hay_scatter_level">
            <option value="none">None</option>
            <option value="trace">Trace</option>
            <option value="light">Light</option>
            <option value="moderate">Moderate</option>
            <option value="heavy">Heavy</option>
            <option value="unknown">Unknown</option>
          </select>
        </label>
        <label>Scatter bale equivalent <input id="hay_scatter_bale_equivalent" type="number" min="0" max="1" step="0.01"></label>
      </div>
      <h3>Overall Hay Quality</h3>
      <div class="grid2">
        <label>Hay color / quality
          <select id="hay_color_quality">
            <option value="normal">Normal coloration</option>
            <option value="bright_fresh">Bright / fresh</option>
            <option value="dark_weathered">Dark / weathered</option>
            <option value="mixed">Mixed</option>
            <option value="unknown">Unknown</option>
          </select>
        </label>
      </div>
      <h3>Flags</h3>
      <div class="checks">
        <label><input id="new_bales_put_out" type="checkbox"> New bales put out</label>
        <label><input id="poor_visibility" type="checkbox"> Poor visibility</label>
      </div>
      <h3>Odd Sightings</h3>
      <div class="checks" id="odd_sightings">
        <label><input type="checkbox" value="person"> Person</label>
        <label><input type="checkbox" value="vehicle"> Vehicle</label>
        <label><input type="checkbox" value="deer"> Deer</label>
        <label><input type="checkbox" value="hog"> Hog</label>
        <label><input type="checkbox" value="equipment"> Equipment</label>
        <label><input type="checkbox" value="camera_blocked"> Camera blocked</label>
      </div>
      <div class="grid2" style="margin-top:12px">
        <label>Visibility
          <select id="visibility">
            <option value="clear">Clear</option>
            <option value="dim">Dim</option>
            <option value="night">Night</option>
            <option value="rain">Rain</option>
            <option value="blocked">Blocked</option>
            <option value="unknown">Unknown</option>
          </select>
        </label>
        <label>Label confidence
          <select id="label_confidence">
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </label>
      </div>
      <label style="margin-top:12px">Notes <textarea id="notes" rows="5" placeholder="Example: three fresh bales, cows not in frame, bale 2 mostly consumed"></textarea></label>
      <div class="actions">
        <button id="save" class="primary">Save Label</button>
        <button id="clear">Clear Form</button>
      </div>
      <div class="status" id="status"></div>
    </section>
  </main>
  <script>
    let images = [];
    let index = 0;
    const baleIds = [1, 2, 3, 4];
    const baleFieldSuffixes = [
      'remaining_percent', 'location', 'condition', 'color_quality',
      'scatter_level', 'scatter_bale_equivalent', 'visibility',
      'level_confidence', 'occlusion_level', 'occluded_by', 'occlusion_note'
    ];
    const baleCheckSuffixes = ['present', 'hay_ring_visible', 'scatter_present'];
    const fields = [
      'round_bales_visible', 'bale_equivalents_remaining', 'hay_days_remaining', 'cattle_count',
      'cow_count', 'calf_count', 'bull_count',
      ...baleIds.flatMap(slot => baleFieldSuffixes.map(suffix => `bale_${slot}_${suffix}`)),
      'bale_4_position_note',
      'hay_scatter_level', 'hay_scatter_bale_equivalent', 'hay_color_quality',
      'visibility', 'label_confidence', 'notes'
    ];
    const checks = [
      'no_bales_confirmed', 'cattle_present', 'new_bales_put_out', 'poor_visibility',
      ...baleIds.flatMap(slot => baleCheckSuffixes.map(suffix => `bale_${slot}_${suffix}`)),
      'hay_scatter_present'
    ];

    function $(id) { return document.getElementById(id); }
    function current() { return images[index]; }
    function fmtDate(value) {
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
    }
    function setStatus(text) { $('status').textContent = text || ''; }

    function applyRangePreset() {
      const value = $('range_preset').value;
      if (!value) return;
      const [start, end] = value.split(':');
      $('start').value = start;
      $('end').value = end;
    }

    async function loadImages() {
      applyRangePreset();
      const params = new URLSearchParams({
        start: $('start').value,
        end: $('end').value,
        limit: $('limit').value || '100',
        unlabeled: $('unlabeled').value
      });
      const response = await fetch('/api/images?' + params.toString());
      images = await response.json();
      index = 0;
      renderList();
      renderImage();
      setStatus(`${images.length} images loaded`);
    }

    function renderList() {
      $('list').innerHTML = images.map((image, i) => {
        const labeled = image.label ? '<span class="badge">labeled</span>' : '<span>unlabeled</span>';
        const mode = image.image_mode === 'source' ? '<span>source queue</span>' : '<span>TOPHAND</span>';
        return `<div class="item ${i === index ? 'active' : ''}" data-index="${i}">
          <img src="${image.public_url}" alt="">
          <div><strong>${fmtDate(image.captured_at)}</strong><span>${image.temperature_text || ''} ${labeled}</span>${mode}</div>
        </div>`;
      }).join('');
      document.querySelectorAll('.item').forEach(node => {
        node.addEventListener('click', () => {
          index = Number(node.dataset.index);
          renderList();
          renderImage();
        });
      });
    }

    function clearForm() {
      fields.forEach(id => { $(id).value = ''; });
      $('visibility').value = 'clear';
      $('label_confidence').value = 'high';
      $('hay_scatter_level').value = 'none';
      $('hay_color_quality').value = 'normal';
      baleIds.forEach(slot => {
        $(`bale_${slot}_location`).value = slot === 1 ? 'left' : slot === 2 ? 'middle' : slot === 3 ? 'right' : 'unknown';
        $(`bale_${slot}_condition`).value = 'unknown';
        $(`bale_${slot}_color_quality`).value = 'normal';
        $(`bale_${slot}_scatter_level`).value = 'none';
        $(`bale_${slot}_visibility`).value = 'clear';
        $(`bale_${slot}_level_confidence`).value = 'high';
        $(`bale_${slot}_occlusion_level`).value = 'none';
        $(`bale_${slot}_occluded_by`).value = 'none';
      });
      checks.forEach(id => { $(id).checked = false; });
      document.querySelectorAll('#odd_sightings input').forEach(node => { node.checked = false; });
      updateDerivedFields();
      updateNoBalesState();
    }

    function loadLabel(label) {
      clearForm();
      if (!label) return;
      fields.forEach(id => {
        if (label[id] !== undefined && label[id] !== null) $(id).value = label[id];
      });
      checks.forEach(id => { $(id).checked = Boolean(label[id]); });
      (label.bale_slots || []).forEach(slotLabel => {
        const slot = Number(slotLabel.slot);
        if (!baleIds.includes(slot)) return;
        const mappings = {
          present: 'present',
          location: 'location',
          remaining_percent: 'remaining_percent',
          condition: 'condition',
          color_quality: 'color_quality',
          hay_ring_visible: 'hay_ring_visible',
          scatter_present: 'scatter_present',
          scatter_level: 'scatter_level',
          scatter_bale_equivalent: 'scatter_bale_equivalent',
          visibility: 'visibility',
          level_confidence: 'level_confidence',
          occlusion_level: 'occlusion_level',
          occluded_by: 'occluded_by',
          occlusion_note: 'occlusion_note'
        };
        Object.entries(mappings).forEach(([source, suffix]) => {
          const id = `bale_${slot}_${suffix}`;
          if ($(id) && slotLabel[source] !== undefined && slotLabel[source] !== null) {
            if ($(id).type === 'checkbox') $(id).checked = Boolean(slotLabel[source]);
            else $(id).value = slotLabel[source];
          }
        });
        if (slot === 4 && slotLabel.position_note) $('bale_4_position_note').value = slotLabel.position_note;
      });
      const odd = new Set(label.odd_sightings || []);
      document.querySelectorAll('#odd_sightings input').forEach(node => { node.checked = odd.has(node.value); });
      updateDerivedFields();
      updateNoBalesState();
    }

    function renderImage() {
      const image = current();
      if (!image) {
        $('image').removeAttribute('src');
        $('meta').textContent = 'No images loaded';
        clearForm();
        return;
      }
      $('image').src = image.public_url;
      $('image').alt = image.path;
      const mode = image.image_mode === 'source' ? 'raw source' : 'TOPHAND branded';
      const range = image.queue_range ? `<span>${image.queue_range}</span>` : '';
      $('meta').innerHTML = `<strong>${fmtDate(image.captured_at)}</strong><span>${image.temperature_text || ''}</span><span>${mode}</span>${range}<span>${image.path}</span>`;
      loadLabel(image.label);
    }

    function numberValue(id) {
      const value = $(id).value;
      return value === '' ? null : Number(value);
    }

    function textValue(id) {
      const value = $(id).value.trim();
      return value === '' ? null : value;
    }

    function animalTotal() {
      return ['cow_count', 'calf_count', 'bull_count'].reduce((total, id) => total + (numberValue(id) || 0), 0);
    }

    function updateDerivedFields() {
      const total = animalTotal();
      $('cattle_count').value = total || '';
      if (total > 0) $('cattle_present').checked = true;
    }

    function updateNoBalesState() {
      const noBales = $('no_bales_confirmed').checked;
      const baleFields = [
        'round_bales_visible', 'bale_equivalents_remaining',
        ...baleIds.flatMap(slot => [
          `bale_${slot}_present`,
          `bale_${slot}_remaining_percent`,
          `bale_${slot}_location`,
          `bale_${slot}_condition`,
          `bale_${slot}_color_quality`,
          `bale_${slot}_hay_ring_visible`,
          `bale_${slot}_scatter_present`,
          `bale_${slot}_scatter_level`,
          `bale_${slot}_scatter_bale_equivalent`,
          `bale_${slot}_visibility`,
          `bale_${slot}_level_confidence`,
          `bale_${slot}_occlusion_level`,
          `bale_${slot}_occluded_by`,
          `bale_${slot}_occlusion_note`
        ]),
        'bale_4_position_note'
      ];
      if (noBales) {
        $('round_bales_visible').value = 0;
        $('bale_equivalents_remaining').value = 0;
        baleIds.forEach(slot => { $(`bale_${slot}_remaining_percent`).value = 0; });
        baleIds.forEach(slot => {
          $(`bale_${slot}_present`).checked = false;
          $(`bale_${slot}_hay_ring_visible`).checked = false;
          $(`bale_${slot}_scatter_present`).checked = false;
          $(`bale_${slot}_scatter_level`).value = 'none';
          $(`bale_${slot}_scatter_bale_equivalent`).value = '';
          $(`bale_${slot}_occlusion_level`).value = 'none';
          $(`bale_${slot}_occluded_by`).value = 'none';
          $(`bale_${slot}_occlusion_note`).value = '';
        });
      }
      baleFields.forEach(id => {
        if (id === 'round_bales_visible') return;
        $(id).disabled = noBales;
      });
    }

    function updateBaleSlotState(slot) {
      if (numberValue(`bale_${slot}_remaining_percent`) !== null) $(`bale_${slot}_present`).checked = true;
      const scatterLevel = $(`bale_${slot}_scatter_level`).value;
      if (scatterLevel && scatterLevel !== 'none') $(`bale_${slot}_scatter_present`).checked = true;
      if ((numberValue(`bale_${slot}_scatter_bale_equivalent`) || 0) > 0) $(`bale_${slot}_scatter_present`).checked = true;
      if ($(`bale_${slot}_present`).checked) $('no_bales_confirmed').checked = false;
      updateNoBalesState();
    }

    function baleSlot(slot) {
      const present = $('no_bales_confirmed').checked
        ? false
        : ($(`bale_${slot}_present`).checked || numberValue(`bale_${slot}_remaining_percent`) !== null);
      return {
        slot,
        present,
        location: $(`bale_${slot}_location`).value,
        remaining_percent: numberValue(`bale_${slot}_remaining_percent`),
        condition: $(`bale_${slot}_condition`).value,
        color_quality: $(`bale_${slot}_color_quality`).value,
        hay_ring_visible: $(`bale_${slot}_hay_ring_visible`).checked,
        scatter_present: $(`bale_${slot}_scatter_present`).checked,
        scatter_level: $(`bale_${slot}_scatter_level`).value,
        scatter_bale_equivalent: numberValue(`bale_${slot}_scatter_bale_equivalent`),
        visibility: $(`bale_${slot}_visibility`).value,
        level_confidence: $(`bale_${slot}_level_confidence`).value,
        occlusion_level: $(`bale_${slot}_occlusion_level`).value,
        occluded_by: $(`bale_${slot}_occluded_by`).value,
        occlusion_note: textValue(`bale_${slot}_occlusion_note`),
        position_note: slot === 4 ? textValue('bale_4_position_note') : null
      };
    }

    function baleFlatFields(slots) {
      const flat = {};
      slots.forEach(slotData => {
        const prefix = `bale_${slotData.slot}`;
        flat[`${prefix}_present`] = slotData.present;
        flat[`${prefix}_location`] = slotData.location;
        flat[`${prefix}_remaining_percent`] = slotData.remaining_percent;
        flat[`${prefix}_condition`] = slotData.condition;
        flat[`${prefix}_color_quality`] = slotData.color_quality;
        flat[`${prefix}_hay_ring_visible`] = slotData.hay_ring_visible;
        flat[`${prefix}_scatter_present`] = slotData.scatter_present;
        flat[`${prefix}_scatter_level`] = slotData.scatter_level;
        flat[`${prefix}_scatter_bale_equivalent`] = slotData.scatter_bale_equivalent;
        flat[`${prefix}_visibility`] = slotData.visibility;
        flat[`${prefix}_level_confidence`] = slotData.level_confidence;
        flat[`${prefix}_occlusion_level`] = slotData.occlusion_level;
        flat[`${prefix}_occluded_by`] = slotData.occluded_by;
        flat[`${prefix}_occlusion_note`] = slotData.occlusion_note;
      });
      flat.bale_4_position_note = textValue('bale_4_position_note');
      return flat;
    }

    function buildPayload() {
      const image = current();
      const odd = [...document.querySelectorAll('#odd_sightings input:checked')].map(node => node.value);
      const baleSlots = baleIds.map(slot => baleSlot(slot));
      const labelPath = image.source_path || image.path;
      updateDerivedFields();
      return {
        schema_version: 'pastucha_hay_label_v3',
        path: labelPath,
        display_path: image.path,
        branded_path: image.image_mode === 'branded' ? image.path : null,
        image_mode: image.image_mode || 'branded',
        source_path: image.source_path || null,
        device: image.device,
        camera_title: image.camera_title,
        captured_at: image.captured_at,
        temperature_text: image.temperature_text || null,
        no_bales_confirmed: $('no_bales_confirmed').checked,
        round_bales_visible: numberValue('round_bales_visible'),
        ...baleFlatFields(baleSlots),
        bale_slots: baleSlots,
        bales: baleSlots,
        bale_equivalents_remaining: numberValue('bale_equivalents_remaining'),
        hay_days_remaining: numberValue('hay_days_remaining'),
        hay_scatter_present: $('hay_scatter_present').checked,
        hay_scatter_level: $('hay_scatter_level').value,
        hay_scatter_bale_equivalent: numberValue('hay_scatter_bale_equivalent'),
        hay_color_quality: $('hay_color_quality').value,
        cattle_present: $('cattle_present').checked,
        cattle_count: numberValue('cattle_count'),
        cow_count: numberValue('cow_count'),
        calf_count: numberValue('calf_count'),
        bull_count: numberValue('bull_count'),
        new_bales_put_out: $('new_bales_put_out').checked,
        poor_visibility: $('poor_visibility').checked,
        odd_sightings: odd,
        visibility: $('visibility').value,
        label_confidence: $('label_confidence').value,
        notes: $('notes').value.trim()
      };
    }

    async function saveLabel() {
      if (!current()) return;
      const response = await fetch('/api/label', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(buildPayload())
      });
      if (!response.ok) {
        setStatus(await response.text());
        return;
      }
      const saved = await response.json();
      images[index].label = saved;
      renderList();
      setStatus('Saved');
    }

    $('load').addEventListener('click', loadImages);
    $('range_preset').addEventListener('change', () => { applyRangePreset(); loadImages(); });
    $('save').addEventListener('click', saveLabel);
    $('clear').addEventListener('click', clearForm);
    $('no_bales_confirmed').addEventListener('change', updateNoBalesState);
    ['cow_count', 'calf_count', 'bull_count'].forEach(id => $(id).addEventListener('input', updateDerivedFields));
    baleIds.forEach(slot => {
      $(`bale_${slot}_present`).addEventListener('change', () => updateBaleSlotState(slot));
      $(`bale_${slot}_remaining_percent`).addEventListener('input', () => updateBaleSlotState(slot));
      $(`bale_${slot}_scatter_level`).addEventListener('change', () => updateBaleSlotState(slot));
      $(`bale_${slot}_scatter_bale_equivalent`).addEventListener('input', () => updateBaleSlotState(slot));
    });
    $('prev').addEventListener('click', () => { if (index > 0) { index -= 1; renderList(); renderImage(); } });
    $('next').addEventListener('click', () => { if (index < images.length - 1) { index += 1; renderList(); renderImage(); } });
    document.addEventListener('keydown', event => {
      if (event.key === 'ArrowLeft') $('prev').click();
      if (event.key === 'ArrowRight') $('next').click();
      if ((event.metaKey || event.ctrlKey) && event.key === 's') { event.preventDefault(); saveLabel(); }
    });
    loadImages();
  </script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    index: ImageIndex
    labels: LabelStore

    def send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_text(self, text: str, status: int = HTTPStatus.OK, content_type: str = "text/plain") -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_text(html_page(), content_type="text/html")
            return
        if parsed.path == "/api/images":
            params = parse_qs(parsed.query)
            self.send_json(self.index.query(params, self.labels))
            return
        if parsed.path == "/api/reload":
            self.index.reload()
            self.send_json({"ok": True, "count": len(self.index.images)})
            return
        self.send_text(f"Not found: {html.escape(parsed.path)}", status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/label":
            self.send_text("Not found", status=HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            saved = self.labels.upsert(payload)
        except Exception as exc:  # noqa: BLE001
            self.send_text(str(exc), status=HTTPStatus.BAD_REQUEST)
            return
        self.send_json(saved)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def main() -> int:
    args = parse_args()
    branding.load_env_file(args.env)
    client = branding.SupabaseRest(
        branding.require_env("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"),
        branding.require_env("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY"),
    )
    args.data_dir.mkdir(parents=True, exist_ok=True)
    source_queue = args.source_queue or (args.data_dir / "source_queue.json")
    Handler.index = ImageIndex(client, args.manifest_path, args.source_bucket, source_queue)
    Handler.labels = LabelStore(args.data_dir)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Pastucha Hay labeler: http://{args.host}:{args.port}/")
    print(f"Images indexed: {len(Handler.index.images)}")
    print(f"Data dir: {args.data_dir}")
    print(f"Source queue: {source_queue}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
