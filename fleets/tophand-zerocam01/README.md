# tophand-zerocam01 - Single Camera Fleet

Single Pi Zero 2 W + IMX708 Camera Module 3 trail camera with Quectel BG95-M3 LTE-M cellular uplink.

## Hardware (verified on tophand-zero-04)

- Raspberry Pi Zero 2 W (aarch64, 512MB RAM)
- IMX708 Camera Module 3 (Wide 120)
- 15-to-22 pin CSI ribbon cable adapter
- Quectel BG95-M3 LTE-M/NB-IoT modem (USB, firmware BG95M3LAR02A03)
- Hologram SIM card (APN: `hologram`, roaming on T-Mobile)

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

## balena Config Variables

Set these in the fleet Configuration tab:

```
BALENA_HOST_CONFIG_camera_auto_detect = 1
BALENA_HOST_CONFIG_dtoverlay = "vc4-kms-v3d","imx708"
BALENA_HOST_CONFIG_dtparam = "i2c_arm=on","audio=on"
BALENA_HOST_CONFIG_enable_uart = 1
BALENA_HOST_CONFIG_gpu_mem = 128
```

## Services

- **camera** - Captures images via rpicam-still, uploads to Supabase storage

## Modem (Quectel BG95-M3)

- USB device: `2c7c:0700` (Quectel LPWA Module)
- Kernel driver: `option`
- Ports: `/dev/ttyUSB0` (diag), `/dev/ttyUSB1` (nmea), `/dev/ttyUSB2` (at/primary)
- ModemManager plugin: `quectel`
- GSM connection: NetworkManager with APN `hologram`
- See `config/hologram.nmconnection` for connection file

## Reference Device: tophand-zero-04

This fleet's config was captured from a working Pi Zero 2W running Raspberry Pi OS (Debian trixie) with camera + BG95-M3 modem both operational. Key details:

- Tailscale IP: 100.76.232.7
- Local IP: 192.168.1.164
- SSH: `ssh pi-zero-04` (via ~/.ssh/config)
- Kernel: 6.12.47+rpt-rpi-v8
- ModemManager: 1.24.0, rpicam-apps: 1.11.0
