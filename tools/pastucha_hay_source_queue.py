#!/usr/bin/env python3
"""Build a fast raw-source image queue for Pastucha Hay labeling.

This intentionally skips TOPHAND branding and overlay OCR. The original source
image already contains the Spypoint overlay, so it can be labeled immediately.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any

import tophand_branding_worker as branding


CAMERA_ID = "FLEX-M-MGE4"
CAMERA_TITLE = "Pastucha Hay"
DEFAULT_DATA_DIR = Path("/home/travis/tophand-instances/sdco/research/pastucha-hay")
DEFAULT_RANGES = [
    "jan17-22:2026-01-17:2026-01-22",
    "jan23-30:2026-01-23:2026-01-30",
    "feb15-21:2026-02-15:2026-02-21",
    "mar04-12:2026-03-04:2026-03-12",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Pastucha Hay raw source queue.")
    parser.add_argument("--env", type=Path, default=Path("/home/travis/tophand-instances/sdco/.secrets/dtzay-supabase.env"))
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-bucket", default=branding.SOURCE_BUCKET)
    parser.add_argument("--range", action="append", dest="ranges", default=[], help="label:YYYY-MM-DD:YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--min-bytes", type=int, default=10_000)
    return parser.parse_args()


def filename_capture_time(path: str) -> dt.datetime | None:
    match = re.search(r"_(20\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", path)
    if not match:
        return None
    year, month, day, hour, minute = map(int, match.groups())
    try:
        return dt.datetime(year, month, day, hour, minute, tzinfo=branding.CAPTURE_TZ)
    except ValueError:
        return None


def parse_range(raw: str) -> tuple[str, dt.date, dt.date]:
    try:
        label, start, end = raw.split(":", 2)
        start_date = dt.date.fromisoformat(start)
        end_date = dt.date.fromisoformat(end)
    except ValueError as exc:
        raise SystemExit(f"Invalid --range {raw!r}; expected label:YYYY-MM-DD:YYYY-MM-DD") from exc
    if end_date < start_date:
        raise SystemExit(f"Invalid --range {raw!r}; end is before start")
    return label, start_date, end_date


def main() -> int:
    args = parse_args()
    branding.load_env_file(args.env)
    client = branding.SupabaseRest(
        branding.require_env("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"),
        branding.require_env("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY"),
    )

    ranges = [parse_range(raw) for raw in (args.ranges or DEFAULT_RANGES)]
    source_objects = branding.list_source_objects(client, args.source_bucket, args.limit, args.min_bytes, {CAMERA_ID})
    images: list[dict[str, Any]] = []

    for source in source_objects:
        captured_at = filename_capture_time(source.path)
        if not captured_at:
            continue
        for label, start, end in ranges:
            if start <= captured_at.date() <= end:
                images.append(
                    {
                        "path": source.path,
                        "source_path": source.path,
                        "name": source.name,
                        "device": CAMERA_ID,
                        "camera_title": CAMERA_TITLE,
                        "captured_at": captured_at.isoformat(),
                        "created_at": source.created_at,
                        "size": source.size,
                        "queue_range": label,
                    }
                )
                break

    images.sort(key=lambda row: row["captured_at"], reverse=True)
    payload = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "source_bucket": args.source_bucket,
        "camera_id": CAMERA_ID,
        "camera_title": CAMERA_TITLE,
        "ranges": [{"label": label, "start": start.isoformat(), "end": end.isoformat()} for label, start, end in ranges],
        "count": len(images),
        "images": images,
    }

    output = args.output or (args.data_dir / "source_queue.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(images)} source queue images to {output}")
    for item in payload["ranges"]:
        count = sum(1 for image in images if image.get("queue_range") == item["label"])
        print(f"{item['label']}: {item['start']} to {item['end']} = {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
