# TopHand Branded Image Pipeline

## Goal

Create a TopHand-branded version of each ranch image while preserving the
original image as the immutable source. The visible bottom overlay printed on
the original image is the final source of truth for capture date, capture time,
temperature, and camera identity.

## Non-Negotiables

- Never use storage `created_at`, file creation time, sync time, upload time, or
  filename time as the final capture timestamp.
- The bottom overlay text printed in the source image wins.
- If OCR/VLM cannot confidently read the source overlay, mark the image for
  review and do not publish a branded version by default.
- Keep originals in `spypoint-images`.
- Publish branded images to a separate bucket, planned as
  `tophand-branded-images`.

## Architecture

1. A 5090 worker reads unbranded source images from Supabase.
2. The worker downloads the original image from `spypoint-images`.
3. It crops the bottom overlay region and runs OCR.
4. If OCR is low confidence, it sends the overlay crop or full image to the VLM
   on 5090 for extraction/verification.
5. It normalizes the extracted values:
   - `overlay_capture_at`
   - `overlay_temperature_f`
   - `overlay_camera_id`
   - `overlay_raw_text`
   - `overlay_confidence`
6. It updates the database record, when the project has `spypoint_images`, so
   `captured_at` reflects the overlay-derived timestamp.
7. It draws a taller TopHand bar over the original bottom overlay.
8. It uploads the result to `tophand-branded-images` with the same logical path.
9. It republishes `tophand-branded-images/manifest.json` for the static viewer.
10. It marks the run `uploaded`, `dry_run`, or `failed` in a JSONL report.

## Proposed Database Fields

For Supabase projects with a `spypoint_images` table, the worker uses the
existing columns:

- `captured_at`: overlay-derived timestamp
- `overlay_versions`: appends `tophand_a1`
- `metadata.tophand_branding_v1`: source path, branded path, raw overlay text,
  overlay timestamp, printed temperature, camera title, model, and run time
- `metadata.capture_time_source`: `image_overlay`

The current Vercel gallery project does not expose `spypoint_images`, so the
side viewer reads the published manifest as its index. That manifest still uses
the overlay-derived timestamp and branded storage path.

## Viewer Change

The Vercel viewer remains static and lightweight:

- Header becomes:
  - `RanchView`
  - `by TOPHAND`
- Main route `/` stays on `spypoint-images`.
- Side route `/tophand` reads `tophand-branded-images/manifest.json`, then loads
  public image URLs from `tophand-branded-images`.
- Filtering, scrolling, and lightbox behavior stay unchanged.
- TOPHAND thumbnails use `object-fit: contain` so the branded overlay is visible
  in the grid, while the main route keeps its original crop behavior.

## Rollout Phases

1. **Preview gate**: generate a small set of visual overlay variants from real
   ranch images and choose the brand treatment.
2. **Schema gate**: add fields/table and a dry-run report that shows what would
   be updated.
3. **Extraction gate**: process 25-50 images, compare OCR/VLM extraction against
   source overlay crops, and tune confidence rules.
4. **Branding gate**: upload 25-50 branded images to `tophand-branded-images`.
5. **Viewer gate**: add `/tophand` without changing `/`.
6. **Backfill**: process the rest in batches with review handling, republishing
   the manifest after each batch.

## Current Preview Variants

The preview tool is `tools/brand_overlay_preview.py`.

The batch worker is `tools/tophand_branding_worker.py`.

Example smoke run on 5090:

```bash
python3 tools/tophand_branding_worker.py \
  --env /home/travis/tophand-instances/sdco/.secrets/dtzay-supabase.env \
  --camera FLEX-M-RJQM \
  --limit 1 \
  --write
```

Generated comparison:

`samples/branding-preview/tophand-overlay-comparison.jpg`

The first preview already confirmed why the overlay must be the source of truth:
the sample filename encodes `18:01`, while the image-imprinted bottom bar reads
`01:01 PM`.
