#!/usr/bin/env python3
"""Add compact VLM scene tags to TOPHAND branded image sidecars.

The branded-image worker owns capture time and temperature extraction from the
printed overlay. This helper enriches those same sidecars with scene-level tags
for the gallery cards and future filters.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover
    requests = None  # type: ignore[assignment]

import tophand_branding_worker as branding


PROMPT = """Inspect the ranch/trail-camera scene in this image.
Ignore the black TOPHAND status bar, timestamps, camera labels, and any printed
overlay text. Return strict JSON only with these keys:

animals_detected: boolean
animal_count: integer
animal_species: array of short lowercase strings
humans_detected: boolean
human_count: integer
vehicles_detected: boolean
vehicle_types: array of short lowercase strings
water_present: boolean
water_level: "high" | "normal" | "low" | "empty" | "unknown" | null
gate_present: boolean
gate_status: "open" | "closed" | "unknown" | null
hay_bales_present: boolean
infrastructure: array of short lowercase strings
scene: 2-5 words
summary: 3-8 words, useful as a gallery chip
alert_priority: "none" | "low" | "medium" | "high"
alert_concerns: array of short strings
confidence_score: number from 0 to 1

Use false, 0, [], "unknown", or null when unsure. Keep wording factual and short.
"""


def image_to_scene_jpeg(image_bytes: bytes, max_width: int) -> bytes:
    image = Image.open(io.BytesIO(image_bytes))
    image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = image.size

    # Remove the branded bottom status bar so the VLM focuses on the ranch scene.
    crop_bottom = max(1, round(height * 0.89))
    image = image.crop((0, 0, width, crop_bottom))

    if image.width > max_width:
        scale = max_width / image.width
        image = image.resize((max_width, max(1, round(image.height * scale))), Image.Resampling.LANCZOS)

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=88, optimize=True)
    return output.getvalue()


def call_ollama_vlm(ollama_url: str, model: str, image_bytes: bytes, timeout: int) -> str:
    payload = {
        "model": model,
        "prompt": PROMPT,
        "images": [base64.b64encode(image_bytes).decode("ascii")],
        "stream": False,
        "options": {"temperature": 0},
    }
    response = requests.post(f"{ollama_url}/api/generate", json=payload, timeout=timeout)
    data = branding.api_json(response)
    return (data or {}).get("response", "")


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise branding.WorkerError(f"VLM did not return JSON: {cleaned[:200]}")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise branding.WorkerError("VLM JSON response was not an object")
    return parsed


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "present", "detected"}
    return bool(value)


def int_value(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def list_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        values = value
    elif isinstance(value, dict):
        values = [key for key, present in value.items() if present]
    else:
        values = re.split(r"[,;/]", str(value))
    return [str(item).strip().lower() for item in values if str(item).strip()]


def enum_value(value: Any, allowed: set[str], fallback: str | None = None) -> str | None:
    if value is None:
        return fallback
    cleaned = str(value).strip().lower().replace("_", " ")
    return cleaned if cleaned in allowed else fallback


def text_value(value: Any, max_chars: int) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value).strip())
    if not text or text.lower() in {"none", "null", "unknown"}:
        return None
    return text[:max_chars].strip()


def normalize_analysis(raw: dict[str, Any], model: str, seconds: float) -> dict[str, Any]:
    confidence = raw.get("confidence_score")
    try:
        confidence_score = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence_score = 0.0

    animal_species = list_value(raw.get("animal_species") or raw.get("species"))
    animal_count = int_value(raw.get("animal_count"))
    animals_detected = bool_value(raw.get("animals_detected")) or animal_count > 0 or bool(animal_species)

    human_count = int_value(raw.get("human_count"))
    humans_detected = bool_value(raw.get("humans_detected")) or human_count > 0

    vehicle_types = list_value(raw.get("vehicle_types"))
    vehicles_detected = bool_value(raw.get("vehicles_detected")) or bool(vehicle_types)

    return {
        "animals_detected": animals_detected,
        "animal_count": animal_count,
        "animal_species": animal_species,
        "humans_detected": humans_detected,
        "human_count": human_count,
        "vehicles_detected": vehicles_detected,
        "vehicle_types": vehicle_types,
        "water_present": bool_value(raw.get("water_present")),
        "water_level": enum_value(raw.get("water_level"), {"high", "normal", "low", "empty", "unknown"}, "unknown"),
        "gate_present": bool_value(raw.get("gate_present")),
        "gate_status": enum_value(raw.get("gate_status"), {"open", "closed", "unknown"}, None),
        "hay_bales_present": bool_value(raw.get("hay_bales_present")),
        "infrastructure": list_value(raw.get("infrastructure")),
        "scene": text_value(raw.get("scene"), 36),
        "summary": text_value(raw.get("summary") or raw.get("short_summary"), 52),
        "alert_priority": enum_value(raw.get("alert_priority"), {"none", "low", "medium", "high"}, "none"),
        "alert_concerns": list_value(raw.get("alert_concerns")),
        "confidence_score": round(confidence_score, 2),
        "analysis_model": model,
        "analysis_seconds": round(seconds, 2),
        "analysis_source": "tophand_vlm_enricher",
        "analyzed_at": dt.datetime.now(dt.UTC).isoformat(),
    }


def load_manifest(client: branding.SupabaseRest, bucket: str, manifest_path: str) -> dict[str, Any]:
    manifest = client.download_json_optional(bucket, manifest_path)
    if not manifest:
        raise branding.WorkerError(f"Could not load {bucket}/{manifest_path}")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich TOPHAND branded gallery sidecars with scene VLM data.")
    parser.add_argument("--env", type=Path, default=Path("/home/travis/tophand-instances/sdco/.secrets/dtzay-supabase.env"))
    parser.add_argument("--bucket", default=branding.DEST_BUCKET)
    parser.add_argument("--manifest-path", default="manifest.json")
    parser.add_argument("--limit", type=int, default=18)
    parser.add_argument("--camera", action="append", help="Only analyze this camera/device. May be repeated.")
    parser.add_argument("--model", default="qwen2.5vl:32b")
    parser.add_argument("--ollama-url", default=None)
    parser.add_argument("--vlm-timeout", type=int, default=240)
    parser.add_argument("--max-width", type=int, default=1280)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--no-manifest", action="store_true")
    parser.add_argument("--report", type=Path, default=Path("tophand-vlm-enrichment-report.jsonl"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if requests is None:
        raise branding.WorkerError("Install the Python 'requests' package before running this tool.")

    branding.load_env_file(args.env)
    args.ollama_url = branding.normalize_ollama_url(
        args.ollama_url or os.environ.get("OLLAMA_URL") or os.environ.get("OLLAMA_HOST")
    )

    client = branding.SupabaseRest(
        branding.require_env("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"),
        branding.require_env("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY"),
    )
    manifest = load_manifest(client, args.bucket, args.manifest_path)
    camera_filter = set(args.camera or [])

    candidates = []
    for image in manifest.get("images", []):
        if camera_filter and image.get("device") not in camera_filter:
            continue
        metadata = client.download_json_optional(args.bucket, branding.branded_metadata_path(image["path"])) or {}
        if metadata.get("analysis") and not args.force:
            continue
        candidates.append((image, metadata))
        if len(candidates) >= args.limit:
            break

    print(f"Queued {len(candidates)} branded images for scene enrichment")
    args.report.parent.mkdir(parents=True, exist_ok=True)

    summary = {"enriched": 0, "failed": 0, "dry_run": 0}
    for index, (image, metadata) in enumerate(candidates, start=1):
        result: dict[str, Any] = {
            "path": image.get("path"),
            "camera_title": image.get("camera_title"),
            "status": "started",
        }
        try:
            source_bytes = client.download(args.bucket, image["path"])
            scene_bytes = image_to_scene_jpeg(source_bytes, args.max_width)
            started = time.time()
            raw_text = call_ollama_vlm(args.ollama_url, args.model, scene_bytes, args.vlm_timeout)
            raw = extract_json_object(raw_text)
            analysis = normalize_analysis(raw, args.model, time.time() - started)
            metadata["analysis"] = analysis

            result.update(
                {
                    "status": "dry_run",
                    "summary": analysis.get("summary"),
                    "animals_detected": analysis.get("animals_detected"),
                    "water_present": analysis.get("water_present"),
                    "gate_status": analysis.get("gate_status"),
                    "confidence_score": analysis.get("confidence_score"),
                    "analysis_seconds": analysis.get("analysis_seconds"),
                }
            )

            if args.write:
                client.upload_bytes(
                    args.bucket,
                    branding.branded_metadata_path(image["path"]),
                    json.dumps(metadata, separators=(",", ":"), sort_keys=True).encode("utf-8"),
                    "application/json",
                )
                result["status"] = "enriched"

            summary[result["status"]] = summary.get(result["status"], 0) + 1
            print(
                f"[{index}/{len(candidates)}] {result['status']}: {image.get('camera_title')} "
                f"{image.get('captured_at')} -> {analysis.get('summary')}"
            )
        except Exception as exc:  # noqa: BLE001
            summary["failed"] += 1
            result.update({"status": "failed", "error": str(exc)})
            print(f"[{index}/{len(candidates)}] failed: {image.get('path')}: {exc}", file=sys.stderr)

        with args.report.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, sort_keys=True) + "\n")

    if args.write and not args.no_manifest:
        manifest_count = branding.publish_manifest(client, args.bucket, 5000)
        print(f"Manifest updated: {manifest_count} branded images")

    print("Summary:", json.dumps(summary, sort_keys=True))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
