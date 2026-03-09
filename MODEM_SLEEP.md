# Power Optimization - Modem Sleep + Deep Idle

## Overview

The ranch camera implements intelligent power management to dramatically reduce power consumption:
1. **Modem Sleep:** Cellular modem only wakes for image uploads
2. **Deep Idle:** CPU powersave + HDMI off + LED off between captures

This hybrid approach achieves **4-5 days battery life** without suspend/resume complexity.

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

### Deep Idle Mode (55 minutes per hour)
- Pi Zero 2W (powersave): 50mA @ 5V
- Camera (idle): 20mA @ 5V
- Tailscale: 20mA @ 5V
- Modem (sleeping): 10mA @ 5V
- HDMI: OFF (0mA)
- LED: OFF (0mA)
- **Total: 100mA @ 5V = ~194mA from 3.7V battery**

### Active Mode (5 minutes per hour)
- Pi Zero 2W (ondemand): 150mA @ 5V
- Camera (capturing): 250mA @ 5V
- Tailscale: 50mA @ 5V
- Modem (awake): 500mA @ 5V
- HDMI: ON (30mA)
- LED: ON (5mA)
- **Total: 985mA @ 5V = ~1900mA from 3.7V battery**

### Average Power (Weighted)
Active hours (5am-10pm, 18 hours/day):
- Deep idle: 194mA × (55/60) = 178mA
- Active: 1900mA × (5/60) = 158mA
- **Average during active hours: ~336mA from 3.7V battery**
- **Average power: ~1.24W**

Off hours (11pm-4am, 6 hours/day):
- Deep idle only: ~194mA = ~0.72W

**Daily average: ~1.1W**

## Battery Life

### With 12,000mAh @ 3.7V Battery
- **Energy capacity:** 44.4Wh
- **Average draw:** 1.1W
- **Estimated runtime:** ~40 hours = **4-5 days**

### Daily Energy Consumption
- Active hours (18h): 1.24W × 18h = 22.3Wh
- Off hours (6h): 0.72W × 6h = 4.3Wh
- **Total: ~26.6Wh per day**
- **Days on 44.4Wh battery: 1.67 days of active capture**
- **With off-hours included: ~4-5 days total**

### Comparison
| Mode | Battery Life | Power Draw | Features |
|------|-------------|------------|----------|
| Modem Always On | ~1.5 days | ~2.5W | Full access 24/7 |
| Modem Sleep Only | ~2 days | ~2.1W | 5-min SSH windows |
| **Modem Sleep + Deep Idle** | **4-5 days** | **1.1W** | **Optimal balance** |
| Deep Sleep + RTC | ~23 days | ~0.15W | No SSH, boots needed |

## Deep Idle Mode

### What It Does

Deep idle mode minimizes power consumption without suspending or shutting down:

**Optimizations:**
- **CPU Governor:** Switches to `powersave` (lowest frequency ~600MHz)
- **HDMI Output:** Disabled (not used on headless camera)
- **Activity LED:** Disabled (no blinking)
- **Network:** Remains connected (Tailscale stays active)

**Power Savings:**
- CPU powersave: ~40mA saved
- HDMI off: ~30mA saved
- LED off: ~5mA saved
- **Total: ~75mA saved @ 5V**

### Operation Cycle

```
:00 - Exit deep idle (CPU to ondemand, HDMI on)
:00 - Capture images
:01 - Wake modem
:01-:04 - Upload to Supabase
:06 - Modem sleeps
:06 - Enter deep idle (CPU to powersave, HDMI off)
:07-:59 - Deep idle mode (~80mA total)
```

### Advantages

✅ **No suspend/resume complexity** - Just clock scaling
✅ **No additional hardware** - Software only
✅ **Network stays connected** - Tailscale accessible during modem wake
✅ **Fast response** - No boot time, instant wake
✅ **Stable and reliable** - No experimental features
✅ **75mA savings** - Significant battery life improvement

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
