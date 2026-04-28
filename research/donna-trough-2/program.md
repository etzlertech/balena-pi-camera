# Donna Trough 2 Intelligence Program

Camera: `YV`
Camera title: Donna Trough 2

## Purpose

Donna Trough 2 is a stable trough scene with overlapping water, hay, and animal
identity signals. Its job is not just to say "animal present." The useful ranch
intelligence is:

- whether the water trough has visible water
- visible water level and water quality
- whether the float/pipe assembly appears normal
- whether the single possible round bale is visible
- how much usable hay remains when the bale is visible
- hay color and scatter/residue condition
- cattle counts split into cows, calves, and bulls
- horse count and horse presence
- whether the distinctive longhorn cow is present
- odd sightings or equipment/feed objects that affect interpretation

As with Pastucha Hay, the printed image overlay is the source of truth for
capture date, time, and temperature. File creation, upload, sync, and manifest
times are not training truth.

## Initial Image Survey

Survey date: 2026-04-27

Source bucket: `spypoint-images`
Camera folder: `YV`

Found `1,278` YV source images:

- newest object: `2026-04-15T15:45:48.298Z`
- oldest object: `2026-01-17T21:23:19.826Z`
- monthly counts: Jan `629`, Feb `211`, Mar `188`, Apr `250`

The current stable Donna Trough 2 composition appears to begin around
2026-01-19. Earlier January YV images include other scenes such as pond, pen,
pasture, and yard views. Those should not be mixed into the Donna Trough 2
training set unless they are explicitly marked as camera-moved/out-of-scope.

Representative sampled frames:

- `YV/PICT1935_S_2026041515430s0zN.jpg` — horse near trough, water visible
- `YV/PICT1936_S_202604151543jaFoZ.jpg` — longhorn cow near trough, water visible
- `YV/PICT1930_S_202604142342zCpHT.jpg` — horse grazing, trough visible
- `YV/PICT1278_S_202603061642ehwDB.jpg` — single round bale visible in background
- `YV/PICT1918_S_202604140542qz65k.jpg` — night frame with trough and animal

## Scene-Specific Observations

The trough is fixed in the front-right foreground. The water surface is often
visible, but level estimates can be blocked by trough rim, glare, float/pipe
hardware, animal bodies, or night infrared washout. We should label water
confidence separately from the level estimate.

The bale is intermittent and appears in the left/background hay area. The
maximum expected bale count is one. The labeler should not ask for four bale
slots here. Instead, it should have one bale object with present/no-bale,
location, visible percent, usable hay equivalent, color quality, scatter, and
occlusion/confidence fields.

Horses are common enough that they need their own count. They should not inflate
cattle counts. The model needs explicit examples of horses close to the trough,
horses grazing in the background, and mixed horse/cattle frames.

The distinctive longhorn cow should be tracked as a scene-specific identity
signal. Initial label should be `longhorn_cow_present`; later we can graduate to
individual animal recognition if markings stay consistent enough.

There is sometimes a black tub or feed/mineral object in the field. This should
be captured as an optional feed-object field so it does not confuse the model
into calling it water or hay.

## Golden Label Schema

Each golden label should include:

- `water_trough_visible`
- `water_visible`
- `water_level_percent`
- `water_level_category` (`full`, `high`, `mid`, `low`, `empty`, `unknown`)
- `water_quality` (`clear`, `normal`, `muddy`, `algae`, `dark`, `unknown`)
- `water_confidence`
- `float_pipe_visible`
- `float_pipe_condition` (`normal`, `possibly_damaged`, `not_visible`, `unknown`)
- `trough_occlusion_level`
- `trough_occluded_by`
- `bale_present`
- `no_bale_confirmed`
- `bale_remaining_percent`
- `bale_equivalent_remaining`
- `bale_location` (`left_background`, `center_background`, `other`, `unknown`)
- `bale_color_quality` (`bright`, `normal`, `dark`, `weathered`, `unknown`)
- `bale_scatter_present`
- `bale_scatter_level` (`none`, `light`, `moderate`, `heavy`, `unknown`)
- `bale_occlusion_level`
- `bale_occluded_by`
- `hay_confidence`
- `cattle_present`
- `cow_count`
- `calf_count`
- `bull_count`
- `cattle_count`
- `horse_present`
- `horse_count`
- `longhorn_cow_present`
- `other_animals`
- `feed_tub_visible`
- `odd_sightings`
- `visibility` (`clear`, `partial`, `night_ir`, `blurred`, `weather_obscured`)
- `label_confidence`
- `notes`

Draft production sidecar shape:

```json
{
  "analysis": {
    "donna_trough_2": {
      "scene": "water_trough_hay_area",
      "water": {
        "trough_visible": true,
        "water_visible": true,
        "level_percent": 75,
        "level_category": "high",
        "quality": "normal",
        "confidence": "medium",
        "float_pipe_visible": true,
        "float_pipe_condition": "normal",
        "occlusion_level": "light",
        "occluded_by": []
      },
      "hay": {
        "bale_present": true,
        "no_bale_confirmed": false,
        "remaining_percent": 55,
        "bale_equivalent_remaining": 0.55,
        "location": "left_background",
        "color_quality": "normal",
        "scatter_present": true,
        "scatter_level": "moderate",
        "occlusion_level": "none",
        "occluded_by": [],
        "confidence": "medium"
      },
      "animals": {
        "cattle_present": true,
        "cow_count": 1,
        "calf_count": 0,
        "bull_count": 0,
        "cattle_count": 1,
        "horse_present": true,
        "horse_count": 1,
        "longhorn_cow_present": false,
        "other_animals": []
      },
      "feed_objects": {
        "feed_tub_visible": true
      },
      "odd_sightings": [],
      "visibility": "clear",
      "confidence_score": 0.82
    }
  }
}
```

## Labeling Strategy

Build a Donna Trough 2 labeler as a separate camera mode, not as a Pastucha Hay
variant. The UI should reuse the proven patterns:

- raw source queue requires overlay-verified capture time
- draft values prefill when available
- `Save Draft`
- top and bottom save buttons
- fast single-click negatives

Donna Trough 2 needs two fast common-case actions:

- `No Bale + Save`
- `Water OK + Save`

The first golden set should be balanced, not just newest images:

- 40 clear trough-only frames
- 30 bale-visible frames across fresh/partial/weathered stages
- 30 horse frames
- 30 longhorn cow frames
- 30 mixed cattle/horse frames
- 20 night/low-confidence frames
- 20 occluded trough or occluded bale frames

The first training pass should score water and hay separately. A model can be
good at trough water and weak at distant bale estimation, so one aggregate score
would hide the failure.

## AutoResearch Scoring

Primary metrics:

- water-visible accuracy
- water-level absolute error
- water-quality accuracy
- bale-present accuracy
- bale-remaining absolute error
- no-bale-confirmed accuracy
- cow-count, calf-count, bull-count, and horse-count error
- longhorn-present accuracy
- invalid JSON rate

Secondary metrics:

- feed-tub false positives
- water/hay confusion rate
- cattle/horse confusion rate
- confidence calibration on night and occluded frames

## Next Build Step

Create a configurable version of the Pastucha labeler/source queue that can run
camera-specific schemas. The first two modes should be:

- `pastucha-hay` (`FLEX-M-MGE4`)
- `donna-trough-2` (`YV`)

Until then, Donna Trough 2 can safely start with a dedicated source queue and
dedicated labeler route/port using the schema above.
