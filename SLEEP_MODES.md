# Pi Zero Sleep Mode Options

## Current Setup: Always-On (Recommended for Your Use Case)

**Status:** Pi stays awake 24/7
**Power:** ~500mW continuous
**WiFi Hotspot:** Always available
**Cellular:** Always connected
**Camera:** Captures on schedule (5am-10pm hourly)

✅ **Pros:**
- WiFi hotspot always accessible in the field
- No wake-up complexity
- Reliable scheduled captures
- Simple, proven design

❌ **Cons:**
- Higher power consumption
- Requires larger battery or more frequent charging

---

## Sleep Mode Options (If Power is Critical)

### Option 1: RTC Wake (Hardware Timer) ⭐ Best for Sleep

**How it works:** Use hardware RTC (Real-Time Clock) to wake Pi at scheduled times

**Hardware Needed:**
- DS3231 or PCF8523 RTC module (~$5-10)
- Wired to GPIO pins
- Connected to Pi shutdown/wake pins

**Pros:**
- Most reliable wake method
- No user interaction needed
- Precise timing

**Cons:**
- Requires additional hardware
- **WiFi hotspot UNAVAILABLE during sleep**
- More complex setup

**Implementation:**
```bash
# Schedule wake at 4:55am, sleep after 10pm capture
# RTC alarm wakes Pi 5 minutes before first capture
```

---

### Option 2: Wake-on-Cellular (Theoretical)

**How it works:** Cellular modem sends wake signal to Pi

**Pros:**
- No additional hardware
- Could wake remotely via SMS/call

**Cons:**
- **Very complex to implement**
- May not work reliably with 2G modem
- **WiFi hotspot UNAVAILABLE during sleep**
- Not proven on Pi Zero 2W + BG95-M3

**Status:** Not recommended for this project

---

### Option 3: Bluetooth Wake (Not Suitable)

**How it works:** Bluetooth pairing with phone to wake Pi

**Pros:**
- Could wake from phone in field

**Cons:**
- **Requires phone pairing in advance**
- **Must be within Bluetooth range (~30 feet)**
- **Unreliable in remote field deployment**
- **WiFi hotspot UNAVAILABLE during sleep**

**Status:** Not recommended for trail camera

---

### Option 4: GPIO Button Wake (User Doesn't Want)

**How it works:** Physical button press wakes Pi

**Pros:**
- Simple, reliable
- Cheap hardware

**Cons:**
- **Requires physical access to camera**
- **User explicitly doesn't want this**

**Status:** Rejected per user requirements

---

## Power Optimization Without Full Sleep

### Light Sleep During Off-Hours (Compromise Solution)

Keep Pi awake but reduce power between captures:

**Active Mode (5am-10pm):**
- Full power
- WiFi hotspot ON
- Cellular connected
- Captures every hour

**Light Sleep (11pm-4am):**
- WiFi hotspot ON (still accessible!)
- Cellular connected
- CPU idled
- No captures
- ~30% power reduction

**Implementation:**
```bash
# No code changes needed
# Pi naturally idles when inactive
# WiFi/cellular stay connected
```

✅ **Pros:**
- WiFi hotspot ALWAYS available
- Simple (already working)
- Some power savings
- No wake complexity

❌ **Cons:**
- Not as much power savings as deep sleep

---

## Recommendation for Your Setup

**Keep current always-on design** because:

1. **WiFi hotspot access is critical** for field work
2. **No button wake** means RTC hardware would be needed for deep sleep
3. **18 images/day is light usage** - captures only 6 seconds per hour
4. **Pi idles efficiently** between captures anyway
5. **Simplicity** - proven, working design

### If Power Becomes Critical:

**Option A:** Larger battery
- 10,000mAh power bank = ~20 hours runtime
- 20,000mAh = ~40 hours
- Solar panel for continuous operation

**Option B:** Add RTC wake hardware
- Implement deep sleep 11pm-4am
- Save ~40% power during 7-hour sleep window
- **Trade-off: No WiFi access at night**

---

## Current Power Profile

**Estimated Power Draw:**
- Pi Zero 2W idle: ~100mA @ 5V = 500mW
- WiFi hotspot active: +100mA = 1000mW total
- Cellular 2G idle: +50mA = 1250mW total
- Camera capture (6 sec/hour): negligible

**Runtime on batteries:**
- 5,000mAh USB battery: ~4 hours
- 10,000mAh: ~8 hours
- 20,000mAh: ~16 hours
- With solar: indefinite (10W panel recommended)

---

## Bottom Line

**For trail camera in pasture:**
- ✅ Always-on is simplest and most reliable
- ✅ WiFi hotspot always accessible
- ⚠️ Add solar panel or larger battery for extended runtime
- ❌ Sleep modes sacrifice field access convenience

**Only add RTC sleep if:**
- Power is absolutely critical
- You're OK with no WiFi access at night (11pm-4am)
- You're willing to add hardware and complexity
