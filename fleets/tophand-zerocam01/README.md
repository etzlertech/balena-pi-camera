# tophand-zerocam01 - Single Camera Fleet

Single Pi Zero 2 W + IMX708 Camera Module 3 trail camera.

## Hardware
- Raspberry Pi Zero 2 W (aarch64)
- IMX708 Camera Module 3 (Wide 120)
- 15-to-22 pin CSI ribbon cable adapter
- **Planned**: Quectel BG95 LTE-M modem for cellular uplink

## Deploy

```bash
cd fleets/tophand-zerocam01
balena push tophand-zerocam01
```

## Fleet Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CAPTURE_INTERVAL` | `300` | Seconds between captures |
| `IMAGE_RESOLUTION` | `2304x1296` | Capture resolution |
| `SUPABASE_URL` | - | Supabase project URL |
| `SUPABASE_KEY` | - | Supabase API key |
| `SUPABASE_BUCKET` | `pi-zero-images` | Storage bucket name |

## Services
- **camera** - Captures images via rpicam-still, uploads to Supabase storage

## Device Config (config.txt)
- `camera_auto_detect=0` - Disable auto-detect for reliability
- `dtoverlay=imx708` - Explicit IMX708 overlay
- `dtparam=i2c_arm=on` - I2C bus for camera
