# Pi Trail Camera - Balena Fleet

Containerized trail camera service for Raspberry Pi Zero 2 W fleet with IMX708 (Camera Module 3) cameras.

## Hardware Requirements

- Raspberry Pi Zero 2 W (or Pi 3/4)
- IMX708 Camera Module 3 (Wide 120° recommended)
- 15-22 pin CSI ribbon cable adapter
- Power supply (5V 2.5A recommended)
- Optional: Waveshare SIM7600G-H 4G HAT for cellular connectivity

## Quick Start

### 1. Create Balena Fleet

```bash
# Install Balena CLI
npm install -g balena-cli

# Login to Balena
balena login

# Create a new fleet
balena fleet create pi-trail-camera --type raspberrypizero2-64
```

### 2. Configure Device Variables

In the Balena dashboard, set these fleet variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `CAPTURE_INTERVAL` | Seconds between captures | `300` |
| `IMAGE_RESOLUTION` | Image size (WxH) | `2304x1296` |
| `SUPABASE_URL` | Your Supabase project URL | - |
| `SUPABASE_KEY` | Supabase anon/service key | - |
| `SUPABASE_BUCKET` | Storage bucket name | `pi-zero-images` |

### 3. Flash Device

```bash
# Download and flash balenaOS to SD card
balena os download raspberrypizero2-64 -o balena.img
balena os configure balena.img --fleet pi-trail-camera
# Flash to SD card using balenaEtcher
```

### 4. Deploy Application

```bash
# Clone this repo
git clone https://github.com/etzlertech/balena-pi-camera
cd balena-pi-camera

# Push to your fleet
balena push pi-trail-camera
```

## Camera Configuration

The IMX708 camera requires a device tree overlay. This is handled automatically by balenaOS, but if you have issues:

### Manual config.txt Addition

If needed, add to `/mnt/boot/config.txt` on the device:

```ini
dtparam=i2c_arm=on
camera_auto_detect=0
dtoverlay=imx708
```

## Directory Structure

```
balena-pi-camera/
├── docker-compose.yml      # Balena compose file
├── balena.yml              # Fleet configuration
├── camera-service/
│   ├── Dockerfile.template # Camera container
│   └── scripts/
│       └── capture_upload.py
└── README.md
```

## Available Resolutions

| Resolution | FPS | Use Case |
|------------|-----|----------|
| 1536x864 | 120 | Motion detection |
| 2304x1296 | 56 | Default (balanced) |
| 4608x2592 | 14 | Full resolution |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CAPTURE_INTERVAL` | No | Capture interval in seconds (default: 300) |
| `IMAGE_RESOLUTION` | No | Resolution WxH (default: 2304x1296) |
| `SUPABASE_URL` | For upload | Supabase project URL |
| `SUPABASE_KEY` | For upload | Supabase API key |
| `SUPABASE_BUCKET` | For upload | Storage bucket name |

## Troubleshooting

### No camera detected

```bash
# SSH into device via Balena
balena ssh <device-uuid>

# Check camera
rpicam-hello --list-cameras

# Check I2C
i2cdetect -y 10
```

### Upload failures

Check Supabase credentials are set correctly in fleet variables.

## Multi-Camera Adapter

For multi-camera setups with Arducam Multi-Camera Adapter V2.2:

```ini
# config.txt
camera_auto_detect=0
dtoverlay=camera-mux-4port,cam0-imx708,cam1-imx708
```

## License

MIT

## Credits

Developed for Etzlertech ranch monitoring project.
