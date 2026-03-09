# tophand-zero-04 Field Access Guide

## WiFi Hotspot Access

**Status:** DISABLED (to save battery power)

Images are uploaded to Supabase cloud storage and can be viewed via:
- Supabase dashboard: https://supabase.com/dashboard/project/dtzayqhebbrbvordmabh/storage/buckets/spypoint-images
- Local viewer: Open `spypoint-viewer.html` in browser

## SSH Connection

### Remote Access (via Tailscale)

```bash
ssh pi@100.76.232.7
# or
ssh pi-04
```

## Active Connections

- **Cellular:** 2G GSM via Hologram (ppp0) - **SLEEPS BETWEEN CAPTURES**
- **Tailscale:** VPN (tailscale0) - 100.76.232.7
- **WiFi Hotspot:** DISABLED (for battery conservation)

### Modem Sleep Mode (Battery Optimization)

The cellular modem sleeps between captures to conserve battery power:

- **Modem OFF:** Most of the time (saves ~400-500mA)
- **Modem ON:** 5-minute window during each hourly capture
  - Wakes 1 minute after capture
  - Uploads image (~2-3 minutes)
  - Stays awake for 5 minutes total (allows SSH access)
  - Sleeps automatically (unless keep-awake flag is set)

**Power Savings:** ~95% reduction in modem power consumption

### SSH During Modem Sleep

If you need to SSH in for maintenance:

1. **Wait for next capture window:** Modem wakes hourly at :01 minutes (e.g., 5:01, 6:01, 7:01)
2. **SSH in quickly:** You have a 5-minute window
3. **Keep modem awake:** Run the keep-awake script

```bash
# Keep modem awake for extended maintenance
bash keep_modem_awake.sh

# Or manually:
touch /tmp/keep_modem_awake

# To re-enable sleep:
rm /tmp/keep_modem_awake
```

**Important:** Remember to remove the keep-awake flag when done to save battery!

## Ranch Camera Status

### Check Timer Schedule
```bash
systemctl list-timers ranch-camera.timer
```

### View Recent Captures
```bash
ls -lh /home/pi/camera/archive/
```

### Manual Capture Test
```bash
sudo systemctl start ranch-camera.service
journalctl -u ranch-camera.service -f
```

### View Logs
```bash
journalctl -u ranch-camera.timer -f
journalctl -u ranch-camera.service -n 50
journalctl -u gallery-server.service -n 50
```

### Gallery Server Status
```bash
# Check web server status
systemctl status gallery-server.service

# Restart web server
sudo systemctl restart gallery-server.service

# View gallery images
ls -lh /home/pi/camera/gallery/
```

## Camera Schedule

- **Active Hours:** 5am - 10pm CDT
- **Frequency:** Hourly (18 images/day)
- **HQ Images:** ~820KB saved to SD card
- **Uploads:** ~118KB compressed (via cellular when Supabase configured)

## Network Status

```bash
# Check cellular signal
mmcli -m 0 --signal-get

# Check active connections
nmcli connection show --active

# Check hotspot status
nmcli device show wlan0
```

## Troubleshooting

### Restart Hotspot
```bash
sudo nmcli connection down tophand-hotspot
sudo nmcli connection up tophand-hotspot
```

### Restart Cellular
```bash
sudo nmcli connection down hologram
sudo nmcli connection up hologram
```

### Restart Camera Timer
```bash
sudo systemctl restart ranch-camera.timer
```

## Power Considerations

The Pi runs continuously with:
- WiFi hotspot always broadcasting
- Cellular modem connected
- Camera captures only during scheduled hours (5am-10pm)
- No captures during 11pm-4am to reduce power usage during off-hours
