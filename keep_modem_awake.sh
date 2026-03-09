#!/bin/bash
# Keep Modem Awake Helper Script
# Run this after SSH'ing into the Pi to prevent modem from sleeping during maintenance

KEEP_AWAKE_FLAG="/tmp/keep_modem_awake"

echo "🔧 Modem Keep-Awake Control"
echo "=============================="
echo ""

if [ -f "$KEEP_AWAKE_FLAG" ]; then
    echo "Current status: MODEM AWAKE (maintenance mode)"
    echo ""
    echo "Options:"
    echo "  1) Keep modem awake (already set)"
    echo "  2) Allow modem to sleep (remove flag)"
    echo ""
    read -p "Choice (1/2): " choice

    if [ "$choice" = "2" ]; then
        rm "$KEEP_AWAKE_FLAG"
        echo "✅ Modem will sleep after next capture cycle"
        echo "   (Saves ~400-500mA)"
    else
        echo "✅ Modem will stay awake"
    fi
else
    echo "Current status: MODEM SLEEPING (power save mode)"
    echo ""
    echo "Options:"
    echo "  1) Keep modem awake for maintenance"
    echo "  2) Let modem sleep (default)"
    echo ""
    read -p "Choice (1/2): " choice

    if [ "$choice" = "1" ]; then
        touch "$KEEP_AWAKE_FLAG"
        echo "✅ Modem will stay awake for maintenance"
        echo "   WARNING: Uses ~400-500mA extra power"
        echo ""
        echo "To re-enable sleep mode later:"
        echo "  rm $KEEP_AWAKE_FLAG"
    else
        echo "✅ Modem will continue sleeping between captures"
    fi
fi

echo ""
echo "Check modem status:"
echo "  nmcli connection show --active"
