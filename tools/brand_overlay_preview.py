#!/usr/bin/env python3
"""Generate TopHand-branded overlay previews for ranch images.

This is intentionally a prototype tool: it lets us compare visual treatments on
real images before we build the batch worker that writes to Supabase.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


CAMERA_NAMES = {
    "FLEX-M-MGE4": "Pastucha Hay",
    "FLEX-M-NGEF": "Back Yard",
    "FLEX-M-RJQM": "Ainsworth Gate",
    "FLEX-S-DARK-RJQH": "Cattle Pen",
    "QC": "Pastucha Pond",
    "QN": "Donna Trough 1",
    "YV": "Donna Trough 2",
    "tophand-zero-04": "ZeroCam 04",
}


def find_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default(size=size)


def parse_path_facts(path: Path) -> tuple[str, str, str]:
    """Return date, time, camera from the filename/path as a preview fallback."""
    camera = path.parent.name
    if camera in {"branding-preview", "samples"}:
        camera_match = re.search(r"(FLEX-[A-Z-]+-[A-Z0-9]+|QC|QN|YV|tophand-zero-04)", path.name)
        if camera_match:
            camera = camera_match.group(1)

    match = re.search(r"(\d{4})(\d{2})(\d{2})[_-]?(\d{2})(\d{2})", path.name)
    if not match:
        return "04/26/26", "6:01 PM", camera

    year, month, day, hour, minute = match.groups()
    hour_int = int(hour)
    suffix = "AM" if hour_int < 12 else "PM"
    display_hour = hour_int % 12 or 12
    return f"{month}/{day}/{year[-2:]}", f"{display_hour}:{minute} {suffix}", camera


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, start: int, bold: bool = False) -> ImageFont.ImageFont:
    for size in range(start, 8, -1):
        font = find_font(size, bold=bold)
        width, _ = text_size(draw, text, font)
        if width <= max_width:
            return font
    return find_font(8, bold=bold)


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: str,
    anchor: str = "mm",
) -> None:
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def draw_variant(
    image: Image.Image,
    output: Path,
    variant: str,
    date_text: str,
    time_text: str,
    temp_text: str,
    camera_text: str,
) -> None:
    canvas = image.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas)
    width, height = canvas.size

    bar_h = max(40, round(height * 0.105))
    y0 = height - bar_h

    if variant == "a1":
        bg = "#050505"
        accent = "#d6b56d"
        muted = "#f2f2f2"
        label = "#ffffff"
        draw.rectangle((0, y0, width, height), fill=bg)
        draw.rectangle((0, y0, width, y0 + 3), fill=accent)
    elif variant == "a2":
        bg = "#050505"
        accent = "#d6b56d"
        muted = "#f3ead8"
        label = "#ffffff"
        draw.rectangle((0, y0, width, height), fill=bg)
        draw.rectangle((0, y0, width, y0 + 3), fill=accent)
        draw.rectangle((round(width * 0.36), y0 + 8, round(width * 0.64), height - 8), outline="#2d2a23", width=1)
    elif variant == "a3":
        bg = "#10130f"
        accent = "#d1ad61"
        muted = "#f5f1e7"
        label = "#ffffff"
        draw.rectangle((0, y0, width, height), fill=bg)
        draw.rectangle((0, y0, width, y0 + 4), fill=accent)
        draw.rectangle((0, height - 3, width, height), fill="#6f8f3a")
    else:
        bg = "#0b0b0a"
        accent = "#caa45e"
        muted = "#e8e1d1"
        label = "#fdfdf8"
        draw.rectangle((0, y0, width, height), fill=bg)
        draw.rectangle((0, y0, width, y0 + 4), fill=accent)

    pad = max(14, round(width * 0.025))
    column_w = (width - pad * 2) // 3
    center_x = width // 2
    mid_y = y0 + bar_h // 2

    camera_label = CAMERA_NAMES.get(camera_text, camera_text)
    date_pill = date_text
    time_pill = time_text
    temp_pill = temp_text
    cam_pill = camera_label.upper() if camera_text in CAMERA_NAMES else camera_text
    name_pill = camera_label.upper()

    if variant == "a1":
        left_text = f"{date_pill} | {time_pill} | {temp_pill}"
        right_text = cam_pill
    elif variant == "a2":
        left_text = f"{date_pill} | {time_pill} | {temp_pill}"
        right_text = cam_pill
    elif variant == "a3":
        left_text = f"{date_pill} | {time_pill} | {temp_pill}"
        right_text = cam_pill
    else:
        left_text = f"{date_pill} | {time_pill} | {temp_pill}"
        right_text = cam_pill

    side_start = max(15, round(bar_h * 0.38))
    left_font = fit_font(draw, left_text, column_w, side_start, bold=True)
    right_font = fit_font(draw, right_text, column_w, side_start, bold=True)
    brand_font = fit_font(draw, "TOPHAND", column_w, max(24, round(bar_h * 0.6)), bold=True)

    draw.text((pad, mid_y), left_text, font=left_font, fill=label, anchor="lm")
    draw.text((width - pad, mid_y), right_text, font=right_font, fill=label, anchor="rm")

    if variant == "a2":
        draw_centered_text(draw, (center_x, mid_y - 1), "TOPHAND", brand_font, label)
        underline_w = min(round(column_w * 0.72), text_size(draw, "TOPHAND", brand_font)[0])
        draw.rectangle(
            (center_x - underline_w // 2, mid_y + round(bar_h * 0.24), center_x + underline_w // 2, mid_y + round(bar_h * 0.28)),
            fill=accent,
        )
    elif variant == "a3":
        brand_w, brand_h = text_size(draw, "TOPHAND", brand_font)
        badge_pad_x = 14
        badge_pad_y = 6
        draw.rounded_rectangle(
            (
                center_x - brand_w // 2 - badge_pad_x,
                mid_y - brand_h // 2 - badge_pad_y,
                center_x + brand_w // 2 + badge_pad_x,
                mid_y + brand_h // 2 + badge_pad_y,
            ),
            radius=3,
            fill="#171a12",
            outline=accent,
            width=1,
        )
        draw_centered_text(draw, (center_x, mid_y), "TOPHAND", brand_font, accent)
    elif variant == "a4":
        draw.rectangle((0, y0, width, y0 + 2), fill="#6f8f3a")
        draw.rectangle((0, y0 + 2, width, y0 + 5), fill=accent)
        draw_centered_text(draw, (center_x, mid_y), "TOPHAND", brand_font, "#f0d38b")
    else:
        draw_centered_text(draw, (center_x, mid_y), "TOPHAND", brand_font, accent)

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=92)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate TopHand overlay preview variants.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("samples/branding-preview"))
    parser.add_argument("--date")
    parser.add_argument("--time")
    parser.add_argument("--temp", default="TEMP 82F")
    parser.add_argument("--camera")
    args = parser.parse_args()

    date_text, time_text, camera_text = parse_path_facts(args.image)
    date_text = args.date or date_text
    time_text = args.time or time_text
    camera_text = args.camera or camera_text

    image = Image.open(args.image)
    stem = args.image.stem
    for variant in ("a1", "a2", "a3", "a4"):
        output = args.out_dir / f"{stem}-tophand-{variant}.jpg"
        draw_variant(image, output, variant, date_text, time_text, args.temp, camera_text)
        print(output)


if __name__ == "__main__":
    main()
