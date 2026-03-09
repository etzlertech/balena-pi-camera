# Modem Sleep Mode - Power Optimization

## Overview

The ranch camera implements intelligent modem sleep to dramatically reduce power consumption. The cellular modem only wakes for image uploads, sleeping the rest of the time.

## How It Works

### Capture Cycle (Every Hour from 5am-10pm)

```
:00 - Camera captures images (modem sleeping)
      ├── High-quality image: ~820KB → SD card archive
      └── Compressed image: ~118KB → prepared for upload

:01 - Modem wakes up (5-minute window)
      ├── Cellular connection establishes (~30 seconds)
      ├── Image uploads to Supabase (~2-3 minutes)
      └── Modem stays awake until :06 (allows SSH access)

:06 - Modem sleeps (unless keep-awake flag is set)
      └── Stays sleeping until next capture
```

## Power Consumption

### Modem Sleeping (55 minutes per hour)
- Pi Zero 2W: 150mA @ 5V
- Camera (idle): 50mA @ 5V
- Tailscale: 50mA @ 5V
- Modem (sleeping): 10mA @ 5V
- **Total: 260mA @ 5V = ~500mA from 3.7V battery**

### Modem Awake (5 minutes per hour)
- Pi Zero 2W: 150mA @ 5V
- Camera: 50mA @ 5V
- Tailscale: 50mA @ 5V
- Modem (awake): 500mA @ 5V
- **Total: 750mA @ 5V = ~1450mA from 3.7V battery**

### Average Power (Weighted)
- **~575mA from 3.7V battery**
- **~2.1W continuous**

## Battery Life

### With 12,000mAh @ 3.7V Battery
- **Energy capacity:** 44.4Wh
- **Average draw:** 2.1W
- **Estimated runtime:** ~21 hours (~2 days with safety margin)

### Comparison
| Mode | Battery Life | Modem Usage |
|------|-------------|-------------|
| Modem Always On | ~40 hours | 100% |
| Modem Sleep (current) | ~2 days | 8% (5 min/hour) |
| Deep Sleep + RTC | ~23 days | 2% (capture only) |

## Configuration

### Environment Variables

Set in `ranch-camera.service`:

```bash
# Enable/disable modem sleep
MODEM_SLEEP_ENABLED=true

# Cellular connection name
MODEM_CONNECTION=hologram

# Wake window duration (seconds)
MODEM_WAKE_TIME=300  # 5 minutes
```

### Keep-Awake Flag

Prevents modem from sleeping (for maintenance):

```bash
# Keep modem awake
touch /tmp/keep_modem_awake

# Allow modem to sleep
rm /tmp/keep_modem_awake
```

## SSH Access During Sleep Mode

### Option 1: Wait for Capture Window (Recommended)

The modem wakes hourly during active hours (5am-10pm):

```
5:01 - Modem awake (5-min window)
6:01 - Modem awake (5-min window)
7:01 - Modem awake (5-min window)
...
```

**Steps:**
1. Wait for next capture time (e.g., 5:01am)
2. SSH in via Tailscale: `ssh pi@100.76.232.7`
3. Run maintenance commands
4. Optionally keep modem awake: `bash keep_modem_awake.sh`

### Option 2: Keep Modem Awake Temporarily

If you need extended access:

```bash
# SSH in during a wake window
ssh pi@100.76.232.7

# Keep modem awake for extended session
bash keep_modem_awake.sh
# (select option 1)

# Do your maintenance work...

# When done, allow modem to sleep again
bash keep_modem_awake.sh
# (select option 2)
```

**Warning:** Keeping modem awake drains ~400-500mA extra power!

### Option 3: Manual Modem Wake (Emergency)

If you need immediate access outside capture windows:

```bash
# Requires physical access or pre-scheduled wake
# Not recommended - defeats power optimization purpose
```

## Monitoring

### Check Modem Status

```bash
# Active connections
nmcli connection show --active

# Modem signal strength (when awake)
mmcli -m 0 --signal-get

# Check keep-awake flag
ls -l /tmp/keep_modem_awake
```

### View Logs

```bash
# Real-time capture logs
journalctl -u ranch-camera.service -f

# Recent captures
journalctl -u ranch-camera.service -n 50

# Timer schedule
systemctl list-timers ranch-camera.timer
```

## Troubleshooting

### Modem Won't Wake

```bash
# Check service status
systemctl status ranch-camera.service

# Manual wake attempt
sudo nmcli connection up hologram

# Check modem hardware
mmcli -L
```

### Modem Won't Sleep

```bash
# Check for keep-awake flag
ls -l /tmp/keep_modem_awake

# Remove flag if present
rm /tmp/keep_modem_awake

# Check next capture cycle
journalctl -u ranch-camera.service -f
```

### Upload Failures

```bash
# Check modem connection during wake window
nmcli connection show --active

# Check Supabase connectivity
curl -I https://dtzayqhebbrbvordmabh.supabase.co

# Increase wake time if needed (in ranch-camera.service)
Environment="MODEM_WAKE_TIME=600"  # 10 minutes
```

## Future Enhancements

### Deep Sleep with RTC

For even better battery life (~23 days):

1. Add RTC module (DS3231 or PCF8523)
2. Configure RTC wake alarms
3. Shutdown Pi between captures
4. Wake via RTC interrupt

See `SLEEP_MODES.md` for details.

### Solar Charging

For indefinite runtime:

1. Add 10W solar panel
2. Add MPPT charge controller
3. Add 18650 battery pack (26650mAh or larger)
4. Angle panel for optimal sun exposure

Estimated runtime: **Indefinite** in sunny locations
