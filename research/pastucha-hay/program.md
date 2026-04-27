# Pastucha Hay AutoResearch Program

## Purpose

Pastucha Hay (`FLEX-M-MGE4`) is not a generic pasture camera. Its job is to watch
the round-bale feeding area for SDCO cattle and produce feed intelligence:

- how many round bales are visible
- how much usable hay remains
- whether new bales were placed
- how many days of hay likely remain
- cattle pressure around the hay
- odd sightings such as people, vehicles, deer, hogs, or equipment

The image overlay remains the source of truth for capture date, time, and
temperature. AutoResearch must not use file timestamps as truth.

## Golden Label Goal

Travis reviews a range of Pastucha Hay images and creates the golden dataset.
These labels are the judge for prompt/model work.

Golden labels are stored at:

```text
/home/travis/tophand-instances/sdco/research/pastucha-hay/golden_labels.jsonl
/home/travis/tophand-instances/sdco/research/pastucha-hay/golden_labels.latest.json
```

Each label should capture:

- `no_bales_confirmed`
- `round_bales_visible`
- per-bale-slot fields for `bale_1` through `bale_4`:
  - `present`
  - `location` (`left`, `middle`, `right`, etc.)
  - `remaining_percent`
  - `condition`
  - `color_quality`
  - `hay_ring_visible`
  - `scatter_present`
  - `scatter_level`
  - `scatter_bale_equivalent`
  - `visibility` / occlusion
  - `level_confidence`
  - `occlusion_level`
  - `occluded_by`
  - `occlusion_note`
- `bale_equivalents_remaining`
- `hay_days_remaining`
- scene-level `hay_scatter_present`, `hay_scatter_level`,
  `hay_scatter_bale_equivalent`, and `hay_color_quality`
- `new_bales_put_out`
- `cattle_present`
- `cattle_count`
- `cow_count`, `calf_count`, `bull_count`
- `odd_sightings`
- `visibility`
- `label_confidence`
- `notes`

## Labeling UI

Run on 5090:

```bash
cd /home/travis/tophand-instances/sdco
python3 tools/pastucha_hay_labeler.py \
  --env /home/travis/tophand-instances/sdco/.secrets/dtzay-supabase.env \
  --host 0.0.0.0 \
  --port 8771
```

Then open:

```text
http://100.66.5.91:8771/
```

The UI reads `tophand-branded-images/manifest.json`, filters to
`FLEX-M-MGE4`, blends in any raw source queue from
`source_queue.json`, and writes labels locally on 5090.

To make a range of unbranded source images available quickly, run:

```bash
cd /home/travis/tophand-instances/sdco
python3 tools/pastucha_hay_source_queue.py \
  --env /home/travis/tophand-instances/sdco/.secrets/dtzay-supabase.env \
  --range jan17-22:2026-01-17:2026-01-22 \
  --range jan23-30:2026-01-23:2026-01-30 \
  --range feb15-21:2026-02-15:2026-02-21 \
  --range mar04-12:2026-03-04:2026-03-12 \
  --sample-minutes 360 \
  --vlm-fallback
```

The raw source images keep the original Spypoint overlay visible. The source
queue extracts capture date/time from the printed bottom overlay before an image
becomes labelable. The fast path uses Tesseract on the bottom strip, with VLM
fallback for frames Tesseract cannot parse. The labeler ignores raw source queue
rows unless `overlay_verified` is true, `captured_at` is present, and
`capture_time_source` starts with `image_overlay_`. Filename timestamps are only
candidate hints and cross-checks; training labels use the printed image overlay
date/time. If an extracted overlay time wildly disagrees with the filename hint,
the row is retried with VLM or held out for manual review rather than using the
filename as truth.

Golden labels are keyed to `source_path`, so labels made against raw source
images still attach to later TOPHAND-branded copies.

## Two Vantage Points

Every AutoResearch trial can analyze each image from two views:

- `full`: scene context, cattle, people, vehicles, deer/hogs, visibility
- `hay_zone`: upper scene crop with the TOPHAND overlay removed, focused on bale
  count and hay condition

Future improvement: manually calibrate a tighter ROI for Pastucha Hay if the
camera framing stays stable.

## Candidate Models

Initial model pool on 5090:

- `qwen2.5vl:32b`
- `gemma4:31b`
- `qwen3-vl:latest`
- `llava:34b`

Do not optimize for cost first. Optimize for correctness and useful ranch
judgment.

## Prompt Families

The first AutoResearch run uses:

- `hay_strict_json`: concise structured extraction
- `ranch_hand_estimator`: ranch-context interpretation with bale equivalents
- `two_step_observe_decide`: observations first, final JSON second

Each prompt must return strict JSON so it can be scored.

## Scoring

Each model/prompt/view candidate is scored against the golden labels:

- bale count absolute error
- bale-equivalent absolute error
- hay-days absolute error
- cattle-count absolute error
- cow-count, calf-count, and bull-count error
- cattle-present accuracy
- no-bales-confirmed accuracy
- new-bales event accuracy
- odd-sighting precision/recall
- invalid JSON rate

Primary score is lower-is-better. Invalid JSON receives a heavy penalty.

## Commands

Run a small research pass:

```bash
cd /home/travis/tophand-instances/sdco
python3 tools/pastucha_hay_autoresearch.py \
  --env /home/travis/tophand-instances/sdco/.secrets/dtzay-supabase.env \
  --labels /home/travis/tophand-instances/sdco/research/pastucha-hay/golden_labels.latest.json \
  --limit 20 \
  --models qwen2.5vl:32b qwen3-vl:latest gemma4:31b
```

Outputs:

```text
/home/travis/tophand-instances/sdco/research/pastucha-hay/candidate_outputs/
/home/travis/tophand-instances/sdco/research/pastucha-hay/eval_results/
```

## Production Path

Once a prompt/model pair wins, write Pastucha Hay intelligence into each branded
image sidecar:

```json
{
  "analysis": {
    "hay": {
      "no_bales_confirmed": false,
      "round_bales_visible": 3,
      "bales": [
        {
          "slot": 1,
          "location": "left",
          "present": true,
          "remaining_percent": 80,
          "condition": "mostly_full",
          "color_quality": "normal",
          "hay_ring_visible": true,
          "scatter_present": true,
          "scatter_level": "light",
          "scatter_bale_equivalent": 0.03,
          "visibility": "clear",
          "level_confidence": "high",
          "occlusion_level": "moderate",
          "occluded_by": "cow",
          "occlusion_note": "Cow blocks front edge, but bale still reads mostly full"
        }
      ],
      "bale_equivalents_remaining": 1.6,
      "hay_days_remaining": 3,
      "hay_scatter_present": true,
      "hay_scatter_level": "light",
      "hay_scatter_bale_equivalent": 0.05,
      "hay_color_quality": "normal",
      "cattle_present": true,
      "cattle_count": 7,
      "cow_count": 5,
      "calf_count": 2,
      "bull_count": 0,
      "odd_sightings": [],
      "confidence_score": 0.86
    }
  }
}
```

Then publish `manifest.json` so RanchView can show hay-specific chips and later
filter/report views.
