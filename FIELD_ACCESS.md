# tophand-zero-04 Field Access Guide

## WiFi Hotspot Access

**SSID:** `tophand-pizero-04`
**Password:** `44444444`
**Pi IP Address:** `10.42.0.1`

## Web Gallery Access 🖼️

### View Images from Phone/Laptop

1. Connect to WiFi network: `tophand-pizero-04`
2. Enter password: `44444444`
3. Open browser and go to: **http://10.42.0.1:8080**

**Features:**
- Mobile-friendly design
- One image per row (easy scrolling)
- Newest images first
- Auto-refresh every 5 minutes
- Shows last 50 compressed images (~118KB each)
- Tap refresh button (⟳) to update

## SSH Connection

### From Laptop in Field

1. Connect your laptop to WiFi network: `tophand-pizero-04`
2. Enter password: `44444444`
3. SSH to the Pi:
   ```bash
   ssh pi@10.42.0.1
   ```
4. Or if you have the SSH config set up:
   ```bash
   ssh pi-04
   ```

### From Remote (via Tailscale)

```bash
ssh pi@100.76.232.7
# or
ssh pi-04
```

## Active Connections

- **Cellular:** 2G GSM via Hologram (ppp0)
- **Hotspot:** tophand-pizero-04 (wlan0) - 10.42.0.1/24
- **Tailscale:** VPN (tailscale0) - 100.76.232.7

## Trail Camera Status

### Check Timer Schedule
```bash
systemctl list-timers trail-camera.timer
```

### View Recent Captures
```bash
ls -lh /home/pi/camera/archive/
```

### Manual Capture Test
```bash
sudo systemctl start trail-camera.service
journalctl -u trail-camera.service -f
```

### View Logs
```bash
journalctl -u trail-camera.timer -f
journalctl -u trail-camera.service -n 50
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
sudo systemctl restart trail-camera.timer
```

## Power Considerations

The Pi runs continuously with:
- WiFi hotspot always broadcasting
- Cellular modem connected
- Camera captures only during scheduled hours (5am-10pm)
- No captures during 11pm-4am to reduce power usage during off-hours
