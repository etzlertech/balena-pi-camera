# tophand-zero-04 - Pi Zero Field Testing

Documentation for the tophand-zero-04 Raspberry Pi Zero 2 W cellular trail camera.

## Device Information

**Hostname**: `tophand-zero-04`
**Tailscale IP**: `100.76.232.7`
**Hardware**: Raspberry Pi Zero 2 W
**OS**: Raspberry Pi OS Trixie (Debian 13) - Kernel 6.12.47 aarch64
**Camera**: IMX708 Camera Module 3 Wide (120° FOV)
**Modem**: Quectel BG95-M3 (2G/LTE Cat-M1/NB-IoT)

## Physical Deployment

### Enclosure

**Type**: Custom 3D printed PLA enclosure
**Solar Panels**: Four solar panels mounted on each face of the enclosure
**Design**: RanchCam configuration for outdoor deployment

### LTE Antenna Setup

**Antenna Source**: Sixfab cellular kit (repurposed from another kit)
**Antenna Type**: Adhesive strip LTE antenna
- Flexible flat white rectangular strip
- Visible internal structure: Zigzag metal flat inlay within the flexible white rectangle
- Adhesive backing for mounting

**Antenna Placement** (Sub-optimal):
- Location: Interior wall of 3D printed PLA enclosure
- Position: Vertical edge, mostly at bottom extending to midway up enclosure
- Installation: Sloppily adhered (not carefully positioned)
- Concern: Surrounded by solar panels on all four faces - potential RF interference/blockage from solar panel EMI and plastic enclosure

**Important Note**: Despite the poor antenna placement inside a PLA enclosure surrounded by solar panels, the device achieves:
- 74% signal strength (2G GSM)
- Stable connectivity
- Successful SSH access
- Successful image uploads over cellular

This suggests the 2G GSM signal is robust enough to penetrate the enclosure and work around the suboptimal antenna positioning. LTE Cat-M1 performance may be more affected by this placement and could benefit from external antenna mounting or repositioning.

## Cellular Connection

**SIM Provider**: Hologram
**SIM ICCID**: `89464278206109001636`
**IMSI**: `240422610900163`
**IMEI**: `864200052660678`

**Network**: T-Mobile (roaming via Hologram)
**Technology**: 2G GSM
**Signal Strength**: 74% (good)
**Interface**: `ppp0`
**Local IP**: `10.228.95.252`
**Public IP**: `185.166.245.57` (via T-Mobile)

### Cellular Performance

The device is currently operating on 2G GSM. While the BG95-M3 modem supports LTE Cat-M1, the device defaults to 2G due to:
- Stronger 2G signal availability (74%)
- Broader 2G coverage in remote areas
- T-Mobile's LTE Cat-M1 network may have limited coverage in test location

**Upload Speed**: ~6.8 KB/sec (54 kbps)
**Latency**: 100-325ms
**Connection**: Stable, 0% packet loss

## SSH Access

### Prerequisites

1. **Tailscale VPN**: Install and sign in with Etzlertech account
   - Download: https://tailscale.com/download
   - After installation, you'll have access to the `100.76.232.7` network

2. **SSH Key**: Your public key must be added to `/home/pi/.ssh/authorized_keys` on the Pi

### Authorized Keys

Currently configured keys:
- `travis@macbook` (MacBook)
- `azuread\travisetzler@EtzlerTech-PC` (Windows PC)

### Adding New Computer Access

On the new computer:
```bash
# Check for existing key
cat ~/.ssh/id_ed25519.pub

# If no key exists, generate one
ssh-keygen -t ed25519
```

On the Pi (or from an authorized computer):
```bash
ssh pi@100.76.232.7
echo "PASTE_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### SSH Connection

**Default**:
```bash
ssh pi@100.76.232.7
```

**SSH Config Shortcut** (add to `~/.ssh/config`):
```ini
Host pi-04
    HostName 100.76.232.7
    User pi
    IdentityFile ~/.ssh/id_ed25519
    StrictHostKeyChecking accept-new
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

Then simply:
```bash
ssh pi-04
```

## 2G Cellular Test Results

All tests performed with WiFi disabled (cellular-only mode).

### SSH Performance Over 2G

| Test Type | Response Time | Status |
|-----------|--------------|--------|
| Simple command (`whoami`, `hostname`) | 6.9 seconds | ✅ Excellent |
| Multiple commands (ls, df, free) | 5.2 seconds | ✅ Excellent |
| File operations (create, read, delete) | 4.2 seconds | ✅ Excellent |
| System monitoring (`ps`, `systemctl`) | 3.8 seconds | ✅ Excellent |

**Conclusion**: SSH over 2G GSM provides fully usable remote administration with 4-7 second response times.

### Image Upload Tests

**Test**: Capture and upload 2304x1296 JPEG images over cellular connection

**WiFi Disabled - Cellular Only Mode**

Two successful upload tests were performed with WiFi completely disabled to verify cellular-only operation:

| Test | Image Size | Upload Speed | Upload Time | Result |
|------|-----------|--------------|-------------|--------|
| Test 1 | 801 KB | 6.8 KB/sec (54 kbps) | ~2:00 | ✅ Success |
| Test 2 | 831 KB | 6.1 KB/sec (48 kbps) | 2:16 | ✅ Success |

**Average Performance**:
- Upload speed: ~6.4 KB/sec (51 kbps)
- Upload time for ~800KB image: ~2 minutes
- Packet loss: 0%
- Connection stability: Excellent

**Test Commands**:
```bash
# Disable WiFi (cellular-only mode)
sudo nmcli connection down 'netplan-wlan0-4598 WiFi'

# Capture image
rpicam-still -o cellular_test.jpg --width 2304 --height 1296 -t 2000 --nopreview

# Upload via cellular ppp0 interface
curl --interface ppp0 -F 'file=@cellular_test.jpg' http://httpbin.org/post

# Re-enable WiFi when testing complete
sudo nmcli connection up 'netplan-wlan0-4598 WiFi'
```

**Conclusion**: Despite the suboptimal LTE antenna placement (inside PLA enclosure, surrounded by solar panels, sloppily positioned), 2G GSM provides reliable image upload capability suitable for trail camera deployment. The ~2 minute upload time per image is acceptable for periodic wildlife/security monitoring applications.

### Camera Capabilities

The IMX708 Camera Module 3 supports three modes:

| Mode | Resolution | Frame Rate | Use Case |
|------|-----------|------------|----------|
| 1 | 1536x864 | 120fps | Fast motion detection |
| 2 | 2304x1296 | 56fps | Balanced (default) |
| 3 | 4608x2592 | 14fps | Full resolution |

**Current Configuration**: Mode 2 (2304x1296 @ 56fps)
**Typical Image Size**: 800-850 KB JPEG

## Network Configuration

### Active Connections

```bash
nmcli connection show --active
```

**Cellular**:
- Name: `hologram`
- Type: GSM
- Device: `ttyUSB2` (PPP connection: `ppp0`)
- APN: `hologram`
- State: Connected
- DNS: 8.8.8.8, 8.8.4.4

**WiFi** (currently disabled for testing):
- Name: `netplan-wlan0-4598 WiFi`
- Device: `wlan0`

### WiFi Control

```bash
# Disable WiFi (cellular-only mode)
sudo nmcli connection down 'netplan-wlan0-4598 WiFi'

# Enable WiFi
sudo nmcli connection up 'netplan-wlan0-4598 WiFi'
```

### Routing

**Cellular-only mode**:
```
default dev ppp0 proto static scope link metric 700
```

**WiFi + Cellular mode**:
```
default via 192.168.1.1 dev wlan0 proto dhcp metric 600
default dev ppp0 proto static scope link metric 700
```

WiFi takes priority (lower metric = higher priority).

## System Status

**Uptime**: Stable (device was online ~1h 40m during initial testing)
**Load Average**: 0.00-0.24 (idle to light usage)
**Services**: ModemManager, NetworkManager running

### Modem Status

```bash
mmcli -L          # List modems
mmcli -m 0        # Show modem details
mmcli -b 2        # Show bearer (connection) details
```

## Testing Checklist

- [x] Cellular modem detection (BG95-M3)
- [x] SIM card recognition (Hologram)
- [x] Network registration (T-Mobile)
- [x] Data connection (`ppp0` interface)
- [x] Internet connectivity (ping, curl)
- [x] SSH over cellular
- [x] Camera detection (IMX708)
- [x] Image capture (rpicam-still)
- [x] Image transfer via cellular
- [ ] Automated capture script
- [ ] Supabase upload integration
- [ ] Battery/power optimization
- [ ] Balena deployment

## Next Steps

1. **Supabase Integration**
   - Configure Supabase credentials
   - Create upload script for captured images
   - Test image storage and metadata logging

2. **Automated Capture**
   - Set up systemd timer or cron job
   - Configure capture intervals
   - Implement motion detection (optional)

3. **Power Optimization**
   - Test power consumption (2G vs LTE)
   - Configure sleep modes
   - Optimize capture schedule for battery life

4. **Balena Deployment**
   - Deploy `balena-pi-camera` service
   - Use fleet configuration: `fleets/tophand-zerocam01`
   - Enable remote fleet management

## Troubleshooting

### Modem not detected
```bash
sudo systemctl restart ModemManager
mmcli -L
```

### Connection issues
```bash
# Check modem state
mmcli -m 0 | grep state

# Reconnect cellular
sudo nmcli connection down hologram
sudo nmcli connection up hologram
```

### SSH connection failures
1. Verify Tailscale is connected on client
2. Check Pi is online: `ping 100.76.232.7`
3. Verify SSH key is in `~/.ssh/authorized_keys` on Pi

## References

- [Hologram Dashboard](https://dashboard.hologram.io/) - Search for ICCID: `89464278206109001636`
- [Tailscale Admin](https://login.tailscale.com/admin) - Manage VPN access
- [Quectel BG95-M3 Documentation](https://www.quectel.com/product/lpwa-bg95-series/)
- [IMX708 Camera Module 3](https://www.raspberrypi.com/products/camera-module-3/)

---

**Last Updated**: 2026-03-08
**Status**: Active testing - WiFi disabled, cellular-only mode operational
**Location**: Outdoor deployment in 3D printed solar-powered enclosure
**Deployment Notes**: LTE antenna is suboptimally placed inside PLA enclosure surrounded by solar panels, yet achieving 74% 2G signal and successful image uploads
