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

- **Cellular:** 2G GSM via Hologram (ppp0)
- **Tailscale:** VPN (tailscale0) - 100.76.232.7
- **WiFi Hotspot:** DISABLED (for battery conservation)

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
