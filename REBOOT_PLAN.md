# Pi Reboot Plan - 12:20 PM CDT Today

## Current Situation
- **Time now:** ~10:08 AM CDT
- **Reboot scheduled:** 12:20 PM CDT (~2 hours 12 minutes from now)
- **Issue:** Modem has been asleep since ~9 PM last night
- **Cause:** `sudo nmcli` fails due to missing passwordless sudo permissions
- **Result:** No modem wake, no uploads, no SSH access

## What's Happening Now
- ✅ Pi is running (on battery/solar)
- ✅ Captures happening hourly (saved to SD card)
- ✅ Deep idle mode working (low power)
- ❌ Modem never wakes (sudo permission failure)
- ❌ No uploads to Supabase
- ❌ No SSH access via Tailscale

## Reboot Strategy

### Step 1: Power Cycle (12:20 PM)
**Unplug power, wait 10 seconds, replug**

### Step 2: Wait for Boot (~60 seconds)
Pi will boot and should have modem active briefly during startup before timer kicks in

### Step 3: Connect Quickly (12:21-12:25 PM window)
```bash
# Monitor for connection (run this on your PC starting at 12:21 PM)
while ! ping -n 1 -w 8000 100.76.232.7 > /dev/null 2>&1; do
    echo "Waiting for Pi..."
    sleep 5
done
echo "PI IS ONLINE!"

# SSH in immediately
ssh pi@100.76.232.7

# Keep modem awake FIRST
touch /tmp/keep_modem_awake

# Fix sudo permissions for nmcli
sudo bash -c 'echo "pi ALL=(ALL) NOPASSWD: /usr/bin/nmcli" > /etc/sudoers.d/pi-network'
sudo chmod 0440 /etc/sudoers.d/pi-network

# Verify modem is active
nmcli connection show --active | grep hologram

# Check recent logs
journalctl -u ranch-camera.service -n 100 | grep -E '(Upload|ERROR|modem)'
```

### Step 4: Test Capture & Upload
```bash
# Trigger test capture
sudo systemctl start ranch-camera.service

# Watch logs live
journalctl -u ranch-camera.service -f
```

### Step 5: Verify Uploads
- Check Supabase: https://supabase.com/dashboard/project/dtzayqhebbrbvordmabh/storage/buckets/spypoint-images
- Look for today's images in: `tophand-zero-04/2026/03/09/`

## Backup Plan (If SSH Fails After Reboot)

### Option A: USB Console Cable
If you have a USB-to-serial cable, connect to UART pins

### Option B: SD Card Direct Edit
1. Remove SD card from Pi
2. Insert into computer
3. Edit `/etc/systemd/system/ranch-camera.service`
4. Change: `MODEM_SLEEP_ENABLED=true` → `MODEM_SLEEP_ENABLED=false`
5. Re-insert SD card and boot

### Option C: Wait for Next Capture Window
After reboot, modem might try to wake at next hour (1:01 PM)
Keep trying to connect for 5-10 minutes after :01 mark

## Expected Timeline
```
12:20 PM - Power cycle Pi
12:21 PM - Pi boots, services start
12:22 PM - Modem connects to cellular
12:23 PM - Tailscale connects
12:23-12:25 PM - SSH access window (CONNECT NOW!)
12:25+ PM - Apply fixes above
12:30 PM - Test capture and verify uploads
```

## After Successful Connection

Once fixed, modem will stay awake permanently (we'll re-enable sleep after confirming uploads work).

**Power consumption with modem always on:**
- ~400mA @ 3.7V = ~1.5W
- Battery life: ~2 days on 12,000mAh
- Solar will help extend this

## Files to Check After Fix
- `/home/pi/camera/archive/` - Should have HQ images from all missed captures
- `/home/pi/camera/images/` - Compressed images waiting to upload
- Supabase bucket - Should start receiving uploads after fix

## Commands Ready to Copy-Paste

```bash
# Quick fix sequence (run immediately after SSH)
touch /tmp/keep_modem_awake && \
sudo bash -c 'echo "pi ALL=(ALL) NOPASSWD: /usr/bin/nmcli" > /etc/sudoers.d/pi-network' && \
sudo chmod 0440 /etc/sudoers.d/pi-network && \
echo "✅ Modem will stay awake, sudo permissions fixed!"

# Test capture
sudo systemctl start ranch-camera.service && journalctl -u ranch-camera.service -f
```

## Notes
- Modem has been asleep since ~9 PM (March 8) - about 15+ hours by reboot time
- All captures since then are saved locally but not uploaded
- After fix, we can batch upload missed images if needed
- Deep idle mode is working correctly (CPU powersave functioning)
