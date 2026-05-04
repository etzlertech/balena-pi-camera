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

After a Frigate+ model is available, configure only the model path in `frigate/config.yml`:

```yaml
model:
  path: plus://<model_id>
```

Then expand `objects.track` for Frigate+ labels such as `deer`, `cow`, `horse`, `goat`, `package`, `face`, `license_plate`, and delivery logos. Do not add those labels before the Frigate+ model is active because the current Coral/default model may not support them.

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

## Next Release

After this deploy is proven:

- Add Tailscale sidecar with `TS_AUTHKEY`
- Add NVMe mount and retention volumes
- Enable Frigate recording
- Add remaining Amcrest cameras
- Wire event clips to 5090 VLM pipeline
