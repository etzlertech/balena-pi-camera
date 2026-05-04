# tophand-ranchview - Edge Security NVR Fleet

Raspberry Pi 5 edge security fleet for the Mark Threadgill RanchView MVP.

## Current Release

This release runs the Pi 5 edge baseline:

- `hello` service on host network
- HTTP health endpoint on port `8080`
- `frigate` service on port `8971`
- USB Coral detector configured as `edgetpu` / `usb`
- three Amcrest/Dahua-compatible cameras configured through Balena `FRIGATE_*` env vars
- motion recording enabled with short initial retention

The old `coral-probe` service is kept in the repo as a diagnostic tool, but it is not part of the running compose stack because Frigate owns the Coral.

## Camera Env

Set the camera credentials in Balena, not git:

```powershell
balena env set FRIGATE_RTSP_USER admin --fleet gh_etzlertech/tophand-ranchview --service frigate
balena env set FRIGATE_RTSP_PASSWORD "<camera-password>" --fleet gh_etzlertech/tophand-ranchview --service frigate
```

Defaults baked into the start wrapper:

- `FRIGATE_AMCREST_01_HOST=192.168.1.121`
- `FRIGATE_AMCREST_02_HOST=192.168.1.122`
- `FRIGATE_AMCREST_03_HOST=192.168.1.175`
- `FRIGATE_AMCREST_01_SUBTYPE=1`
- `FRIGATE_AMCREST_02_SUBTYPE=1`
- `FRIGATE_AMCREST_03_SUBTYPE=1`

If the Amcrest substream is not enabled, set `FRIGATE_AMCREST_01_SUBTYPE=0` temporarily and expect heavier CPU usage.

## Frigate+ Env

Set the Frigate+ API key in Balena as a service environment variable, not in git and not in `config.yml`:

```powershell
balena env set PLUS_API_KEY "<frigate-plus-api-key>" --fleet gh_etzlertech/tophand-ranchview --service frigate
```

The Frigate docs require the key to be named `PLUS_API_KEY` in the Docker/Balena environment. After deployment, the Frigate UI should expose the Frigate+ submission controls in Explore.

`snapshots.clean_copy` is explicitly enabled so submitted images can be sent without timestamp/bounding-box overlays. Submit and verify examples before requesting the first tuned model.

Frigate+ subscription status:

- Plan status: active
- Renewal date: 2027-05-03
- Account page showed payment-management and cancellation controls available.
- No payment card details are stored in this repo.

Initial Frigate+ base model selected for the Pi 5 USB Coral:

- Base model: 2026.1
- Name: `yolov9s`
- Size: `320x320`
- Detector type: `edgetpu`
- Train date: 2026-04-14
- Model ID: `be9c11b486ba0e2b8ea13338d4cc66ee`

Configure only the model path in `frigate/config.yml`:

```yaml
model:
  path: plus://be9c11b486ba0e2b8ea13338d4cc66ee
```

The active tracked Frigate+ labels now include `person`, `face`, `license_plate`, `car`, `motorcycle`, `bicycle`, `school_bus`, `dog`, `cat`, `bird`, `deer`, `cow`, `horse`, `goat`, `package`, and delivery-logo attributes. Frigate+ does not currently expose plain `truck` as a supported label; pickups and most trucks should be reviewed as `car`, while supported delivery logos become vehicle attributes.

`license_plate` here means detecting the plate object. Full OCR/plate-character recognition is Frigate LPR, which is disabled by default and should not be assumed safe on the Pi 5 because Frigate documents AVX/AVX2 as a requirement for LPR/recognition workloads. The production path for Threadgill should be:

1. Pi 5 + Coral detects `car`, `motorcycle`, and `license_plate` with the Frigate+ model.
2. Frigate keeps the motion clip and clean snapshot so we do not lose the evidence.
3. The TopHand bridge/upstream worker sends plate snapshots or crops to the 5090 OCR/VLM path for character recognition.
4. The recognized text is written back to Frigate with `POST /api/events/:event_id/recognized_license_plate` and stored in the TopHand event database.
5. The RanchView UI displays `recognized_license_plate` when Frigate events include it.

If native Frigate LPR is tested on x86/5090 instead of the Pi, start with the simplest config and debug saved plates:

```yaml
lpr:
  enabled: true
  device: CPU
  debug_save_plates: true
  min_plate_length: 4
```

Only keep `debug_save_plates` on during tuning because Frigate does not automatically delete those debug crops.

## Deploy

```powershell
cd C:\Users\TravisEtzler\Documents\GitHub\balena-pi-camera\fleets\tophand-ranchview
balena login --web
balena push tophand-ranchview
```

If the fleet slug differs in Balena Cloud, use the slug shown by:

```powershell
balena fleet list
```

## Expected Logs

```text
TopHand RanchView hello service starting
site=mark-threadgill device=<device-name> fleet=<fleet-name> port=8080
heartbeat site=mark-threadgill uptime_seconds=...
TopHand Frigate starting
frigate.detectors.plugins.edgetpu_tfl INFO    : TPU found
```

## 5070 Recording Backup

The `frigate-backup` sidecar mounts `frigate_media` read-only and rsyncs Frigate recordings, clips, snapshots, exports, and a safe SQLite backup copy to the 5070 archive drive:

```text
/data/archive/threadgill/frigate-recordings/
  media/      # Frigate media mirror
  manifests/  # latest sidecar sync manifests
  logs/       # reserved for server-side backup logs
```

Balena env required for the `frigate-backup` service:

```powershell
balena env set TS_AUTHKEY "<tailscale-auth-key>" --fleet gh_etzlertech/tophand-ranchview --service tailscale
balena env set BACKUP_SSH_PRIVATE_KEY_B64 "<base64-ed25519-private-key>" --fleet gh_etzlertech/tophand-ranchview --service frigate-backup
```

Defaults:

- Source: `/media/frigate`
- Destination: `travis@100.120.124.113:/data/archive/threadgill/frigate-recordings/media/`
- Manifest destination: `travis@100.120.124.113:/data/archive/threadgill/frigate-recordings/manifests/`
- Interval: 300 seconds

The backup intentionally does not use `--delete`; remote copies are preserved even if Frigate retention later removes local files. The active Frigate SQLite database is copied through `sqlite3 .backup` before rsync to avoid shipping a half-written DB file.

The backup uses the 5070 Tailscale address, so the `tailscale` sidecar must be authenticated before `frigate-backup` can connect.

## Next Release

After this deploy is proven:

- Add NVMe mount and retention volumes
- Enable Frigate recording
- Add remaining Amcrest cameras
- Wire event clips to 5090 VLM pipeline
