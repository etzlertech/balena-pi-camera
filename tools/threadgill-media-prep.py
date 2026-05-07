#!/usr/bin/env python3
"""Prepare Threadgill clip thumbnails and mobile proxies for remote UI playback.

This reads the additive 5070 Frigate archive, creates tiny card thumbnails and
low-bitrate MP4 previews, writes JSON indexes, then optionally publishes the
prepared static media to the public VPS.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ARCHIVE_ROOT = Path(os.environ.get("THREADGILL_ARCHIVE_ROOT", "/data/archive/threadgill/frigate-recordings/bridge-pull"))
PREPARED_ROOT = Path(os.environ.get("THREADGILL_PREPARED_ROOT", "/data/archive/threadgill/frigate-recordings/prepared"))
PUBLIC_BASE = os.environ.get("THREADGILL_MEDIA_PUBLIC_BASE", "/threadgill-media").rstrip("/")
PUBLISH_DEST = os.environ.get("THREADGILL_MEDIA_PUBLISH_DEST", "root@89.116.191.85:/opt/threadgill-media/")
PUBLISH_ENABLED = os.environ.get("THREADGILL_MEDIA_PUBLISH", "1") == "1"
LOCAL_TZ = ZoneInfo(os.environ.get("THREADGILL_TIMEZONE", "America/Chicago"))
RECENT_HOURS = int(os.environ.get("THREADGILL_MEDIA_RECENT_HOURS", "24"))
ARCHIVE_DAYS = int(os.environ.get("THREADGILL_MEDIA_ARCHIVE_DAYS", "14"))
MAX_PROXY_PER_RUN = int(os.environ.get("THREADGILL_MEDIA_MAX_PROXY_PER_RUN", "80"))
MAX_THUMB_PER_RUN = int(os.environ.get("THREADGILL_MEDIA_MAX_THUMB_PER_RUN", "500"))
MAX_MMS_THUMB_PER_RUN = int(os.environ.get("THREADGILL_MEDIA_MAX_MMS_THUMB_PER_RUN", str(MAX_THUMB_PER_RUN)))
MIN_FILE_AGE_SECONDS = int(os.environ.get("THREADGILL_MEDIA_MIN_FILE_AGE_SECONDS", "45"))
EVENT_MATCH_PAD_SECONDS = int(os.environ.get("THREADGILL_MEDIA_EVENT_MATCH_PAD_SECONDS", "6"))
CAMERA_NAMES = {
    "amcrest_mt2544ew_01": "Zoom Cam 120",
    "amcrest_mt2544ew_02": "Zoom Cam 121",
    "amcrest_2493e_03": "Fixed Dome 122",
    "anpviz_ptz_06": "PTZ Cam 175",
}
CAMERA_ROTATIONS = {
    "amcrest_mt2544ew_01": 180,
    "amcrest_mt2544ew_02": 180,
    "amcrest_2493e_03": 180,
    "anpviz_ptz_06": 180,
}
OBJECT_LABEL_PRIORITY = [
    "person",
    "car",
    "truck",
    "dog",
    "cat",
    "horse",
    "cow",
    "deer",
    "bird",
    "license_plate",
]


def log(message: str) -> None:
    print(f"{datetime.now(LOCAL_TZ).isoformat()} threadgill-media-prep {message}", flush=True)


def run(cmd: list[str], timeout: int = 180) -> bool:
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "ignore").strip().replace("\n", " ")[:240]
        log(f"command_failed code={proc.returncode} cmd={cmd[0]} err={err}")
        return False
    return True


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def public_path(path: Path) -> str:
    rel = path.relative_to(PREPARED_ROOT).as_posix()
    return f"{PUBLIC_BASE}/{rel}"


def parse_stem(path: Path) -> tuple[int, int, int]:
    match = re.match(r"^(\d+)_(\d+)_(\d+)s$", path.stem)
    if not match:
        start = int(path.stat().st_mtime)
        return start, start, 0
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def load_metadata(mp4: Path) -> dict[str, Any]:
    meta_path = mp4.with_suffix(".json")
    if not meta_path.exists():
        return {}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def source_jpg(mp4: Path) -> Path | None:
    jpg = mp4.with_suffix(".jpg")
    return jpg if jpg.exists() and jpg.stat().st_size > 512 else None


def output_paths(camera: str, local_day: str, stem: str) -> tuple[Path, Path, Path]:
    yyyy, mm, dd = local_day.split("-")
    thumb = PREPARED_ROOT / "thumbs" / camera / yyyy / mm / dd / f"{stem}.jpg"
    mms_thumb = PREPARED_ROOT / "mms-thumbs" / camera / yyyy / mm / dd / f"{stem}.jpg"
    proxy = PREPARED_ROOT / "proxies" / camera / yyyy / mm / dd / f"{stem}.mp4"
    return thumb, mms_thumb, proxy


def display_filter(camera: str, base: str) -> str:
    filters = [base]
    rotation = CAMERA_ROTATIONS.get(camera, 0) % 360
    if rotation == 180:
        filters.extend(["hflip", "vflip"])
    return ",".join(filters)


def make_thumb(src_jpg: Path | None, src_mp4: Path, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 512:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp.jpg")
    source = src_jpg or src_mp4
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
    ]
    if not src_jpg:
        cmd.extend(["-ss", "00:00:02"])
    cmd.extend([
        "-i",
        str(source),
        "-frames:v",
        "1",
        "-vf",
        "scale=240:-2",
        "-q:v",
        "7",
        str(tmp),
    ])
    if run(cmd, timeout=90) and tmp.exists() and tmp.stat().st_size > 512:
        tmp.replace(dest)
        return True
    tmp.unlink(missing_ok=True)
    return False


def make_mms_thumb(camera: str, src_jpg: Path | None, src_mp4: Path, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 512:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp.jpg")
    source = src_jpg or src_mp4
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
    ]
    if not src_jpg:
        cmd.extend(["-ss", "00:00:02"])
    cmd.extend([
        "-i",
        str(source),
        "-frames:v",
        "1",
        "-vf",
        display_filter(camera, "scale=240:-2"),
        "-q:v",
        "7",
        str(tmp),
    ])
    if run(cmd, timeout=90) and tmp.exists() and tmp.stat().st_size > 512:
        tmp.replace(dest)
        return True
    tmp.unlink(missing_ok=True)
    return False


def make_proxy(src_mp4: Path, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 1024:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp.mp4")
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(src_mp4),
        "-vf",
        "scale='min(640,iw)':-2",
        "-r",
        "10",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "34",
        "-movflags",
        "+faststart",
        str(tmp),
    ]
    if run(cmd, timeout=240) and tmp.exists() and tmp.stat().st_size > 1024:
        tmp.replace(dest)
        return True
    tmp.unlink(missing_ok=True)
    return False


def iter_recordings() -> list[Path]:
    root = ARCHIVE_ROOT / "recordings"
    if not root.exists():
        return []
    cutoff = time.time() - MIN_FILE_AGE_SECONDS
    files = [path for path in root.rglob("*.mp4") if path.stat().st_size > 1024 and path.stat().st_mtime < cutoff]
    return sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)


def object_title(labels: list[str]) -> str:
    if not labels:
        return "Motion recording"
    ordered = sorted(labels, key=lambda label: OBJECT_LABEL_PRIORITY.index(label) if label in OBJECT_LABEL_PRIORITY else 999)
    if len(ordered) == 1:
        return f"{ordered[0].replace('_', ' ').title()} detected"
    first = ordered[0].replace("_", " ").title()
    return f"{first} + {len(ordered) - 1} more"


def event_score(event: dict[str, Any]) -> float:
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    return max(Number(event.get("top_score")), Number(data.get("top_score")), Number(data.get("score")))


def iter_events() -> list[dict[str, Any]]:
    root = ARCHIVE_ROOT / "events"
    if not root.exists():
        return []

    events: list[dict[str, Any]] = []
    for path in root.rglob("*.json"):
        try:
            event = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(event, dict):
            continue
        camera = str(event.get("camera") or "")
        label = str(event.get("label") or "")
        start = Number(event.get("start_time"))
        end = Number(event.get("end_time")) or start
        if camera not in CAMERA_NAMES or not label or start <= 0:
            continue
        events.append({
            "camera": camera,
            "end": max(end, start),
            "id": str(event.get("id") or path.stem),
            "label": label,
            "score": event_score(event),
            "start": start,
        })
    return sorted(events, key=lambda item: item["start"])


def annotate_object_events(records: list[dict[str, Any]]) -> None:
    events_by_camera: dict[str, list[dict[str, Any]]] = {}
    for event in iter_events():
        events_by_camera.setdefault(event["camera"], []).append(event)

    for record in records:
        camera = str(record.get("camera") or "")
        start = Number(record.get("startTime"))
        end = Number(record.get("endTime"))
        matches = [
            event for event in events_by_camera.get(camera, [])
            if event["start"] <= end + EVENT_MATCH_PAD_SECONDS
            and event["end"] >= start - EVENT_MATCH_PAD_SECONDS
        ]
        if not matches:
            record.setdefault("objectLabels", [])
            continue

        labels = sorted({event["label"] for event in matches})
        record["eventIds"] = [event["id"] for event in matches[:12]]
        record["eventScore"] = max(event["score"] for event in matches)
        record["objectLabels"] = labels
        record["objects"] = max(Number(record.get("objects")), len(matches))
        record["label"] = object_title(labels)
        record["title"] = object_title(labels)


def clip_record(mp4: Path) -> dict[str, Any] | None:
    try:
        rel = mp4.relative_to(ARCHIVE_ROOT / "recordings")
        camera = rel.parts[0]
    except Exception:
        return None
    if camera not in CAMERA_NAMES:
        return None

    meta = load_metadata(mp4)
    start_i, end_i, duration_i = parse_stem(mp4)
    start = float(meta.get("start_time") or start_i)
    end = float(meta.get("end_time") or end_i)
    duration = float(meta.get("duration") or duration_i or max(0, end - start))
    local_dt = datetime.fromtimestamp(start, LOCAL_TZ)
    local_day = local_dt.strftime("%Y-%m-%d")
    thumb, mms_thumb, proxy = output_paths(camera, local_day, mp4.stem)
    motion = Number(meta.get("motion"))

    return {
        "id": f"{camera}:{mp4.stem}",
        "camera": camera,
        "cameraName": CAMERA_NAMES[camera],
        "startTime": start,
        "endTime": end,
        "duration": duration,
        "motion": meta.get("motion"),
        "objects": meta.get("objects"),
        "label": "Motion recording" if motion > 0 else "Recent recording",
        "localDay": local_day,
        "title": "Motion recording" if motion > 0 else "Recent recording",
        "thumbPath": public_path(thumb) if thumb.exists() else "",
        "mmsThumbPath": public_path(mms_thumb) if mms_thumb.exists() else "",
        "proxyPath": public_path(proxy) if proxy.exists() else "",
        "bytes": mp4.stat().st_size,
    }


def Number(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def publish() -> None:
    if not PUBLISH_ENABLED or not PUBLISH_DEST:
        return
    cmd = [
        "rsync",
        "-a",
        "--partial",
        "--mkpath",
        "--protect-args",
        "--exclude=*.tmp*",
        "--timeout=90",
        f"{PREPARED_ROOT.as_posix().rstrip('/')}/",
        PUBLISH_DEST,
    ]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=600)
    if proc.returncode in {0, 24}:
        log(f"publish_complete dest={PUBLISH_DEST}")
    else:
        err = proc.stderr.decode("utf-8", "ignore").strip().replace("\n", " ")[:240]
        log(f"publish_failed code={proc.returncode} err={err}")


def build_indexes(records: list[dict[str, Any]]) -> None:
    now = datetime.now(LOCAL_TZ)
    recent_after = now - timedelta(hours=RECENT_HOURS)
    archive_after = now - timedelta(days=ARCHIVE_DAYS)
    recent_records = [
        row for row in records
        if datetime.fromtimestamp(float(row["startTime"]), LOCAL_TZ) >= recent_after
    ]
    archive_records = [
        row for row in records
        if datetime.fromtimestamp(float(row["startTime"]), LOCAL_TZ) >= archive_after
    ]

    common = {
        "site": "mark-threadgill",
        "generatedAt": now.isoformat(),
        "publicBase": PUBLIC_BASE,
        "preparedBy": "tophand5070",
    }
    write_json(PREPARED_ROOT / "index.json", {
        **common,
        "windowHours": RECENT_HOURS,
        "clips": recent_records,
    })

    by_day: dict[str, list[dict[str, Any]]] = {}
    for row in archive_records:
        by_day.setdefault(str(row["localDay"]), []).append(row)
    for day, rows in by_day.items():
        write_json(PREPARED_ROOT / "archive" / f"{day}.json", {
            **common,
            "day": day,
            "clips": rows,
        })


def main() -> int:
    PREPARED_ROOT.mkdir(parents=True, exist_ok=True)
    mp4s = iter_recordings()
    thumbs_made = 0
    mms_thumbs_made = 0
    proxies_made = 0

    for mp4 in mp4s:
        record = clip_record(mp4)
        if not record:
            continue
        thumb, mms_thumb, proxy = output_paths(record["camera"], record["localDay"], mp4.stem)
        src_jpg = source_jpg(mp4)
        if thumbs_made < MAX_THUMB_PER_RUN and make_thumb(src_jpg, mp4, thumb):
            thumbs_made += 1
        if mms_thumbs_made < MAX_MMS_THUMB_PER_RUN and make_mms_thumb(record["camera"], src_jpg, mp4, mms_thumb):
            mms_thumbs_made += 1
        if proxies_made < MAX_PROXY_PER_RUN and make_proxy(mp4, proxy):
            proxies_made += 1
        if (
            thumbs_made >= MAX_THUMB_PER_RUN
            and mms_thumbs_made >= MAX_MMS_THUMB_PER_RUN
            and proxies_made >= MAX_PROXY_PER_RUN
        ):
            break

    records = [row for row in (clip_record(mp4) for mp4 in mp4s) if row and row.get("thumbPath")]
    annotate_object_events(records)
    build_indexes(records)
    publish()
    log(f"complete clips={len(records)} thumbs_made={thumbs_made} mms_thumbs_made={mms_thumbs_made} proxies_made={proxies_made}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
