# Balena Skills & Knowledge Base

Comprehensive reference for building, deploying, and managing balenaCloud IoT fleets. Written so any agent or developer can come in fresh and become productive immediately.

---

## Table of Contents

1. [Platform Overview](#platform-overview)
2. [balena CLI Reference](#balena-cli-reference)
3. [Dockerfile & Build System](#dockerfile--build-system)
4. [docker-compose.yml for Balena](#docker-composeyml-for-balena)
5. [balena.yml Fleet Manifest](#balenayml-fleet-manifest)
6. [Variables & Configuration](#variables--configuration)
7. [Device Types & Architecture](#device-types--architecture)
8. [Hardware Access](#hardware-access)
9. [Camera Systems](#camera-systems)
10. [Networking](#networking)
11. [Cellular Connectivity (LTE-M / BG95)](#cellular-connectivity)
12. [Multi-Container Apps](#multi-container-apps)
13. [Persistent Storage](#persistent-storage)
14. [Supervisor API](#supervisor-api)
15. [Releases & OTA Updates](#releases--ota-updates)
16. [Security](#security)
17. [Troubleshooting](#troubleshooting)
18. [Project-Specific Notes](#project-specific-notes)

---

## Platform Overview

balena is a container-based IoT platform. The stack:

- **balenaCloud** - Fleet management dashboard (dashboard.balena-cloud.com)
- **balenaOS** - Minimal Linux OS built on Yocto, runs containers via balenaEngine (Docker-compatible)
- **balena Supervisor** - On-device agent that manages containers, applies updates, exposes local API
- **balena CLI** - Command-line tool for deploying, managing, and debugging devices
- **balenaEngine** - Docker-compatible container runtime optimized for embedded/IoT

### How It Works

1. You write a `docker-compose.yml` + Dockerfiles (one per service)
2. `balena push <fleet>` builds images on balena builders (or locally with `--local`)
3. Built images are pushed to the balena registry
4. The Supervisor on each device pulls the new release and restarts services
5. Delta updates minimize bandwidth (only binary diffs are transferred)

---

## balena CLI Reference

### Installation

```bash
npm install -g balena-cli
```

### Authentication

```bash
balena login              # Interactive login (web, token, or credentials)
balena login --web        # Browser-based login
balena login --token <T>  # Token-based login
balena whoami             # Check current login
```

### Fleet Management

```bash
balena fleets                                     # List all fleets
balena fleet <FLEET>                              # Fleet details
balena fleet create <NAME> --type <DEVICE_TYPE>   # Create fleet
balena fleet rm <FLEET>                           # Delete fleet
balena fleet pin <FLEET> <COMMIT>                 # Pin to release
balena fleet track-latest <FLEET>                 # Unpin, track latest
```

### Deployment

```bash
balena push <FLEET>             # Build on balena builders and deploy
balena push <FLEET> --source .  # Explicit source dir
balena push <IP> --local        # Build + deploy to local device (dev mode)
balena deploy <FLEET> --build   # Build locally, push to registry
balena release <COMMIT>         # Get release info
```

### Device Management

```bash
balena devices                          # List all devices
balena device <UUID>                    # Device details
balena device rename <UUID> <NAME>      # Rename device
balena device rm <UUID>                 # Remove device
balena device pin <UUID> <COMMIT>       # Pin device to release
balena device track-fleet <UUID>        # Unpin device
balena device move <UUID> <FLEET>       # Move device to different fleet
balena device reboot <UUID>             # Reboot
balena device shutdown <UUID>           # Shutdown
balena device identify <UUID>           # Blink LED
```

### SSH & Debugging

```bash
balena ssh <UUID>                       # SSH into host OS
balena ssh <UUID> <SERVICE>             # SSH into specific service container
balena logs <UUID>                      # Stream device logs
balena logs <UUID> --service camera     # Logs for specific service
balena tunnel <UUID> -p 22222:22222     # TCP tunnel to device
```

### Environment Variables

```bash
balena envs --fleet <FLEET>                         # List fleet env vars
balena env add <KEY> <VALUE> --fleet <FLEET>        # Set fleet env var
balena env add <KEY> <VALUE> --device <UUID>        # Set device env var
balena env rm <ID>                                  # Remove env var
balena envs --device <UUID> --service <SVC>         # Service-level vars
```

### OS & Provisioning

```bash
balena os download <TYPE> -o balena.img             # Download OS image
balena os configure balena.img --fleet <FLEET>      # Configure image for fleet
balena os configure balena.img --wifi-ssid <SSID> --wifi-key <KEY>  # With WiFi
balena config read --drive /dev/sdX                 # Read config from SD
balena config write --drive /dev/sdX                # Write config to SD
balena preload balena.img --fleet <FLEET> --commit <COMMIT>  # Preload app into image
```

### Local Development

```bash
balena local scan                       # Discover devices on local network
balena push <IP> --local                # Deploy to local device
balena ssh <IP>                         # SSH to local device
```

---

## Dockerfile & Build System

### Dockerfile.template

Use `Dockerfile.template` for multi-architecture builds. Template variables are replaced at build time:

| Variable | Description | Example |
|----------|-------------|---------|
| `%%BALENA_MACHINE_NAME%%` | Device type slug | `raspberrypi3-64` |
| `%%BALENA_ARCH%%` | Architecture | `aarch64` |

```dockerfile
FROM balenalib/%%BALENA_MACHINE_NAME%%-debian:bookworm

# Or use architecture-based:
FROM balenalib/%%BALENA_ARCH%%-debian:bookworm
```

### Base Images

balena provides base images at `balenalib/<device-or-arch>-<distro>:<version>`:

```
balenalib/raspberrypi3-64-debian:bookworm       # Device-specific
balenalib/raspberrypizero2-64-debian:bookworm    # Pi Zero 2W specific
balenalib/aarch64-debian:bookworm                # Architecture-based
balenalib/raspberrypi3-64-python:3.11-bookworm   # Language stack
balenalib/raspberrypi3-64-node:18-bookworm       # Node.js stack
```

### Build Variants

- `run` (default) - Minimal, for production
- `build` - Includes build tools (gcc, make, etc.)

```dockerfile
FROM balenalib/raspberrypi3-64-debian:bookworm-build AS builder
# ... compile stuff ...

FROM balenalib/raspberrypi3-64-debian:bookworm-run
COPY --from=builder /app /app
```

### Best Practices

- Always clean up apt caches: `apt-get clean && rm -rf /var/lib/apt/lists/*`
- Use multi-stage builds for compiled languages
- Pin package versions for reproducibility
- Use `.dockerignore` to exclude unnecessary files
- For Pi Zero (armv6): use `raspberry-pi` or `raspberrypi0-2w-64` device types

---

## docker-compose.yml for Balena

Balena uses **compose file version 2.1** (not v3). Key differences from standard Docker Compose:

```yaml
version: '2.1'

services:
  camera:
    build: ./camera-service          # Path to Dockerfile/Dockerfile.template
    privileged: true                 # Full hardware access
    restart: always                  # Supervisor restarts on failure
    network_mode: host               # Share host network (optional)
    labels:
      io.balena.features.kernel-modules: '1'   # Access kernel modules
      io.balena.features.firmware: '1'          # Access firmware files
      io.balena.features.dbus: '1'              # Access host D-Bus
      io.balena.features.supervisor-api: '1'    # Access Supervisor API
      io.balena.features.balena-api: '1'        # Access balena API
      io.balena.features.balena-socket: '1'     # Access balenaEngine socket
      io.balena.features.sysfs: '1'             # Access /sys
      io.balena.features.procfs: '1'            # Access /proc
      io.balena.update.strategy: download-then-kill  # Update strategy
      io.balena.update.handover-timeout: '60000'     # For hand-over strategy
    devices:
      - "/dev/video0:/dev/video0"    # Specific device access
      - "/dev/vchiq:/dev/vchiq"      # VideoCore interface
      - "/dev/i2c-1:/dev/i2c-1"     # I2C bus
    volumes:
      - 'captured_images:/data/images'    # Named volume (persistent)
    tmpfs:
      - /tmp                         # RAM-backed tmpfs
    environment:
      - MY_VAR=value                 # Hardcoded
      - DYNAMIC_VAR=${DYNAMIC_VAR}   # From fleet/device env vars
    cap_add:
      - SYS_RAWIO                    # Specific capabilities instead of privileged
    depends_on:
      - another-service

volumes:
  captured_images:                   # Survives container restarts and updates
```

### Update Strategies (via labels)

| Strategy | Label Value | Use Case |
|----------|-------------|----------|
| **download-then-kill** | `download-then-kill` | Default. Downloads new, then swaps. |
| **kill-then-download** | `kill-then-download` | Memory-constrained devices (Pi Zero) |
| **delete-then-download** | `delete-then-download` | Extreme storage constraints |
| **hand-over** | `hand-over` | Zero downtime. Both containers run simultaneously. |

### Balena Labels Reference

| Label | Effect |
|-------|--------|
| `io.balena.features.kernel-modules` | Mounts kernel modules into container |
| `io.balena.features.firmware` | Mounts firmware files |
| `io.balena.features.dbus` | Exposes host D-Bus socket |
| `io.balena.features.supervisor-api` | Exposes Supervisor API + sets BALENA_SUPERVISOR_* vars |
| `io.balena.features.balena-api` | Sets BALENA_API_KEY and BALENA_API_URL |
| `io.balena.features.balena-socket` | Mounts balenaEngine socket |
| `io.balena.features.sysfs` | Bind mounts /sys |
| `io.balena.features.procfs` | Bind mounts /proc |
| `io.balena.features.journal-logs` | Provides access to journal logs |

---

## balena.yml Fleet Manifest

Optional file that defines fleet metadata for balenaHub and deployment:

```yaml
name: my-fleet-name
type: sw.application
version: "1.0.0"
description: >-
  Description of the fleet/application.

assets:
  repository:
    type: blob.asset
    data:
      url: 'https://github.com/user/repo'

data:
  applicationEnvironmentVariables:
    - CAPTURE_INTERVAL: '300'
    - IMAGE_RESOLUTION: '2304x1296'

  defaultDeviceType: raspberrypi3-64
  supportedDeviceTypes:
    - raspberrypi3-64
    - raspberrypizero2-64
```

---

## Variables & Configuration

### Variable Types

| Type | Scope | Prefix | Set Via |
|------|-------|--------|---------|
| **Fleet env var** | All devices in fleet | None | Dashboard, CLI, API |
| **Device env var** | Single device | None | Dashboard, CLI, API |
| **Fleet service var** | Specific service, all devices | None | Dashboard, CLI, API |
| **Device service var** | Specific service, single device | None | Dashboard, CLI, API |
| **Fleet config var** | OS/supervisor config, all devices | `BALENA_` or `RESIN_` | Dashboard, CLI, API |
| **Device config var** | OS/supervisor config, single device | `BALENA_` or `RESIN_` | Dashboard, CLI, API |

### Priority (highest to lowest)

1. Device service variable
2. Fleet service variable
3. Device environment variable
4. Fleet environment variable

### Config Variables for Raspberry Pi (config.txt)

Set via dashboard Configuration tab or CLI. Prefix with `BALENA_HOST_CONFIG_`:

```
BALENA_HOST_CONFIG_gpu_mem = 128
BALENA_HOST_CONFIG_dtoverlay = imx708
BALENA_HOST_CONFIG_dtparam = "i2c_arm=on","spi=on","audio=on"
BALENA_HOST_CONFIG_camera_auto_detect = 0
BALENA_HOST_CONFIG_enable_uart = 1
```

These map directly to lines in `/mnt/boot/config.txt`. The supervisor applies changes and reboots the device.

### Built-in Environment Variables

Available automatically in every container:

| Variable | Description |
|----------|-------------|
| `BALENA_DEVICE_UUID` | Device UUID |
| `BALENA_DEVICE_NAME_AT_INIT` | Initial device name |
| `BALENA_APP_ID` | Fleet/application ID |
| `BALENA_APP_NAME` | Fleet name |
| `BALENA_SERVICE_NAME` | Current service name |
| `BALENA_SUPERVISOR_ADDRESS` | Supervisor API URL |
| `BALENA_SUPERVISOR_API_KEY` | Supervisor API key |
| `BALENA_HOST_OS_VERSION` | balenaOS version |

---

## Device Types & Architecture

### Raspberry Pi Family

| Device | Type Slug | Architecture | Notes |
|--------|-----------|-------------|-------|
| Pi Zero W | `raspberry-pi` | armv6l (32-bit) | Very limited, single-core |
| Pi Zero 2 W | `raspberrypizero2-64` | aarch64 (64-bit) | Quad-core, our primary target |
| Pi 3B/3B+ | `raspberrypi3-64` | aarch64 (64-bit) | Good dev/test platform |
| Pi 4B | `raspberrypi4-64` | aarch64 (64-bit) | Most capable |
| Pi 5 | `raspberrypi5` | aarch64 (64-bit) | Latest |

**Important**: Pi Zero 2 W uses the same SoC as Pi 3 (BCM2710A1), so `raspberrypi3-64` base images work. The dedicated `raspberrypizero2-64` type is preferred for proper device tree and memory management.

---

## Hardware Access

### I2C

Enabled by default in balenaOS (`dtparam=i2c_arm=on`). Access via:

```yaml
# docker-compose.yml - Option 1: specific device
devices:
  - "/dev/i2c-1:/dev/i2c-1"

# Option 2: privileged mode (all devices)
privileged: true
```

Scan for devices: `i2cdetect -y 1`

### SPI

Enabled by default (`dtparam=spi=on`). Access `/dev/spidev0.0` and `/dev/spidev0.1`.

### UART / Serial

Enable in config: `BALENA_HOST_CONFIG_enable_uart = 1`

For Pi 3+ with Bluetooth, remap UART:
```
BALENA_HOST_CONFIG_dtoverlay = pi3-miniuart-bt
```

Serial devices: `/dev/ttyS0` (mini UART) or `/dev/ttyAMA0` (PL011)

### GPIO

Access via `/sys/class/gpio/` or libraries like `RPi.GPIO`, `gpiozero`, `pigpio`. Requires privileged mode or `SYS_RAWIO` capability + sysfs access.

---

## Camera Systems

### IMX708 (Camera Module 3)

Our primary camera. Key config:

```ini
# config.txt (or via BALENA_HOST_CONFIG_ vars)
camera_auto_detect=0          # Disable auto-detect for reliability
dtoverlay=imx708              # Explicit overlay
dtparam=i2c_arm=on            # Required for camera I2C
```

### Capture Commands (libcamera/rpicam-apps)

```bash
rpicam-hello --list-cameras                    # List detected cameras
rpicam-still -o image.jpg --width 2304 --height 1296 -t 2000 --nopreview
rpicam-vid -o video.h264 -t 10000 --width 1920 --height 1080
```

### IMX708 Resolutions

| Resolution | Max FPS | Use Case |
|------------|---------|----------|
| 1536x864 | 120 | Motion detection, fast capture |
| 2304x1296 | 56 | Default balanced mode |
| 4608x2592 | 14 | Full sensor resolution |

### Multi-Camera (Arducam 4-port Mux)

For the tophand-zerocam04 fleet (4x IMX708):

```ini
camera_auto_detect=0
dtoverlay=camera-mux-4port,cam0-imx708,cam1-imx708,cam2-imx708,cam3-imx708
```

Select camera in software: `rpicam-still --camera 0` through `--camera 3`

### Docker Device Access

```yaml
devices:
  - "/dev/video0:/dev/video0"     # V4L2 video device
  - "/dev/vchiq:/dev/vchiq"       # VideoCore (legacy camera stack)
  - "/dev/media0:/dev/media0"     # Media controller
  - "/dev/media1:/dev/media1"
  - "/dev/media2:/dev/media2"
```

Or use `privileged: true` for all device access.

---

## Networking

### Architecture

balenaOS uses **NetworkManager** (since v2.0) with **ModemManager** for cellular.

### WiFi Configuration

Network configs live in `/system-connections/` on the boot partition. Format:

```ini
[connection]
id=my-wifi
type=wifi
autoconnect-priority=10

[wifi]
mode=infrastructure
ssid=MyNetwork

[wifi-security]
auth-alg=open
key-mgmt=wpa-psk
psk=MyPassword

[ipv4]
method=auto

[ipv6]
method=auto
```

### Static IP

```ini
[ipv4]
method=manual
address1=192.168.1.100/24,192.168.1.1
dns=8.8.8.8;8.8.4.4;
```

### Firewall Requirements (Outbound Only)

| Port | Protocol | Purpose |
|------|----------|---------|
| 443 | TCP | Cloudlink, API, web terminal |
| 123 | UDP | NTP time sync |
| 53 | UDP | DNS resolution |

Allowlist: `*.balena-cloud.com`

---

## Cellular Connectivity

### Quectel BG95 (LTE-M / NB-IoT)

The BG95 is our target modem for cellular-connected camera deployments. It supports LTE Cat-M1 (LTE-M) and NB-IoT, ideal for low-bandwidth image upload in remote locations.

### Hardware Connection

The BG95 typically connects via USB or UART:
- **USB**: Appears as `/dev/ttyUSB0-3` (multiple ports for AT, modem, GPS, diagnostics)
- **UART**: Connect to Pi GPIO TX/RX pins

### NetworkManager GSM Configuration

Create a connection file for the cellular modem:

```ini
[connection]
id=cellular
type=gsm
autoconnect=true
autoconnect-priority=0

[gsm]
apn=your-carrier-apn
number=*99#

[serial]
baud=115200

[ipv4]
method=auto

[ipv6]
method=auto
```

### ModemManager

balenaOS includes ModemManager for cellular modem management:

```bash
mmcli -L                          # List modems
mmcli -m 0                        # Modem details
mmcli -m 0 --simple-connect="apn=your-apn"  # Connect
mmcli -m 0 --location-get        # GPS location (if supported)
```

### Docker Access for Modem

```yaml
services:
  camera:
    privileged: true
    labels:
      io.balena.features.dbus: '1'        # For ModemManager
      io.balena.features.kernel-modules: '1'
    devices:
      - "/dev/ttyUSB0:/dev/ttyUSB0"
      - "/dev/ttyUSB1:/dev/ttyUSB1"
      - "/dev/ttyUSB2:/dev/ttyUSB2"
      - "/dev/ttyUSB3:/dev/ttyUSB3"
```

### BG95 AT Commands (Common)

```
AT+CFUN=1               # Full functionality
AT+COPS?                 # Current network operator
AT+CEREG?                # Network registration status
AT+CSQ                   # Signal quality
AT+QENG="servingcell"   # Serving cell info
AT+QCFG="nwscanseq"     # Network scan sequence
AT+QCFG="iotopmode",0   # LTE-M only mode
AT+QCFG="iotopmode",1   # NB-IoT only mode
AT+QCFG="iotopmode",2   # Both (default)
AT+QGPS=1               # Enable GNSS
AT+QGPSLOC=2            # Get GPS location
```

---

## Multi-Container Apps

Each service gets its own directory with a Dockerfile:

```
project/
├── docker-compose.yml
├── service-a/
│   ├── Dockerfile.template
│   └── ...
├── service-b/
│   ├── Dockerfile.template
│   └── ...
```

### Inter-Service Communication

Services can communicate via:
- **Shared named volumes** (files on disk)
- **Docker networking** (service names resolve as hostnames)
- **Host network mode** (`network_mode: host`)

```yaml
version: '2.1'
services:
  camera:
    build: ./camera-service
    volumes:
      - shared_data:/data

  uploader:
    build: ./uploader-service
    volumes:
      - shared_data:/data
    depends_on:
      - camera

volumes:
  shared_data:
```

---

## Persistent Storage

### Named Volumes

Named volumes in `docker-compose.yml` persist across:
- Container restarts
- Application updates
- Service rebuilds

They do **NOT** persist across:
- Device re-provisioning (reflash)
- Volume removal

```yaml
volumes:
  my_data:       # Stored at /mnt/data/docker/volumes/<app>_my_data/
```

### tmpfs (RAM Disk)

For temporary data that doesn't need persistence:

```yaml
tmpfs:
  - /tmp
  - /run
```

---

## Supervisor API

The Supervisor exposes a local HTTP API on each device. Access requires the `io.balena.features.supervisor-api` label.

### Common Endpoints

```bash
# Inside a container:
curl "$BALENA_SUPERVISOR_ADDRESS/v1/device?apikey=$BALENA_SUPERVISOR_API_KEY"

# Device info
GET /v1/device

# Restart service
POST /v2/applications/$BALENA_APP_ID/restart-service
Body: {"serviceName": "camera"}

# Reboot device
POST /v1/reboot

# Shutdown
POST /v1/shutdown

# Purge application data
POST /v1/purge
Body: {"appId": $BALENA_APP_ID}

# Application state
GET /v2/applications/state

# Device state
GET /v2/state/status

# Force update check
POST /v1/update
Body: {"force": true}  # Overrides update locks
```

---

## Releases & OTA Updates

### How Releases Work

1. `balena push` triggers a build on balena builders
2. Successful build creates a new **release** (identified by commit hash)
3. By default, fleets use **rolling releases** (latest auto-deploys)
4. Supervisor on each device detects new release, pulls delta, and updates

### Delta Updates

Available on balenaOS 2.47.1+. Only binary diffs are transferred, dramatically reducing bandwidth. Two types:
- **Build-time deltas**: Auto-generated between last and new release
- **On-demand deltas**: Generated when devices request updates for which no delta exists

### Release Pinning

```bash
# Pin fleet to specific release
balena fleet pin <FLEET> <COMMIT>

# Pin individual device
balena device pin <UUID> <COMMIT>

# Resume tracking latest
balena fleet track-latest <FLEET>
balena device track-fleet <UUID>
```

### Update Locks

Prevent updates during critical operations:

```bash
# In container - create lock file
lockfile /tmp/balena/updates.lock
# ... do critical work ...
rm -f /tmp/balena/updates.lock
```

Python:
```python
from lockfile import LockFile
lock = LockFile("/tmp/balena/updates")
with lock:
    # Critical section - updates blocked
    pass
```

---

## Security

### SSH Access

- **Development images**: SSH enabled by default on port 22222
- **Production images**: SSH only via balenaCloud (balena tunnel)

```bash
balena ssh <UUID>                # Via balenaCloud
balena tunnel <UUID> -p 22222:22222  # Direct tunnel
```

### API Keys

- **Session tokens**: Short-lived, from dashboard login
- **API keys**: Long-lived, created in dashboard Preferences > Access tokens
- **Device API keys**: Auto-generated per device, used by supervisor

### Best Practices

- Use fleet environment variables for secrets (not hardcoded in Dockerfiles)
- Use production images for deployed devices
- Rotate API keys regularly
- Use device-level vars for device-specific secrets

---

## Troubleshooting

### Camera Not Detected

```bash
# SSH into device
balena ssh <UUID> camera

# List cameras
rpicam-hello --list-cameras

# Check I2C bus (camera is on bus 10 for some setups)
i2cdetect -y 1
i2cdetect -y 10

# Check device tree overlays loaded
cat /proc/device-tree/model
ls /proc/device-tree/soc/

# Check video devices
ls -la /dev/video*
ls -la /dev/media*
```

### Common Fixes

| Issue | Fix |
|-------|-----|
| No camera found | Set `camera_auto_detect=0` and explicit `dtoverlay=imx708` |
| Permission denied on /dev | Add `privileged: true` or map specific devices |
| Out of memory during build | Use `kill-then-download` update strategy |
| Upload fails | Check env vars: `SUPABASE_URL`, `SUPABASE_KEY` |
| Device offline | Check power, network, SD card. View logs in dashboard |
| Slow updates | Delta updates enabled? Check `BALENA_SUPERVISOR_DELTA` |
| Container crash loop | Check `balena logs <UUID> --service <svc>` |

### Useful Debug Commands

```bash
# On-device (via balena ssh)
cat /mnt/boot/config.txt                    # Check boot config
dmesg | grep -i camera                      # Kernel camera messages
vcgencmd get_camera                         # Legacy camera check
cat /proc/meminfo                           # Memory status
df -h                                       # Disk usage
journalctl -u balena-supervisor --no-pager  # Supervisor logs
```

---

## Project-Specific Notes

### Repository Structure

This repo houses multiple fleet configurations:

```
balena-pi-camera/
├── fleets/
│   ├── tophand-zerocam01/    # Single cam: Pi Zero 2W + IMX708
│   └── tophand-zerocam04/    # Quad cam: Pi Zero 2W + 4-port mux + 4x IMX708 (planned)
├── BALENA_SKILLS.md          # This file
└── README.md
```

### Fleet: tophand-zerocam01

- **Hardware**: Pi Zero 2W + single IMX708 Camera Module 3
- **Function**: Trail camera - captures images at intervals, uploads to Supabase
- **Future**: Quectel BG95 LTE-M modem for cellular connectivity
- **Deploy**: `cd fleets/tophand-zerocam01 && balena push tophand-zerocam01`

### Fleet: tophand-zerocam04 (Planned)

- **Hardware**: Pi Zero 2W + Arducam 4-port camera mux + 4x IMX708
- **Function**: Multi-angle trail camera
- **Config**: `dtoverlay=camera-mux-4port,cam0-imx708,cam1-imx708,cam2-imx708,cam3-imx708`

### Supabase Integration

Images are uploaded to Supabase Storage with path: `{device_name}/{YYYY}/{MM}/{DD}/{filename}.jpg`

Required fleet variables:
- `SUPABASE_URL` - Project URL
- `SUPABASE_KEY` - API key (anon or service role)
- `SUPABASE_BUCKET` - Storage bucket name

### config.txt for Our Devices

Key settings for IMX708 reliability:
```ini
camera_auto_detect=0      # MUST disable for reliable IMX708 detection
dtoverlay=imx708          # Explicit overlay
dtparam=i2c_arm=on        # I2C for camera communication
enable_uart=1             # UART for modem (future BG95)
```
