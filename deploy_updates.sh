#!/bin/bash
# Deploy Ranch Camera updates to Pi Zero
# Run this script when connected to the Pi (via Tailscale or hotspot)

echo "🐄 Deploying Ranch Camera updates to tophand-zero-04..."

# Check if Pi is reachable
if ! ping -c 1 -W 2 10.42.0.1 &> /dev/null && ! ping -c 1 -W 2 100.76.232.7 &> /dev/null; then
    echo "❌ Pi not reachable. Make sure you're connected via:"
    echo "   - WiFi hotspot: tophand-pizero-04"
    echo "   - or Tailscale VPN"
    exit 1
fi

# Determine which IP to use
if ping -c 1 -W 2 10.42.0.1 &> /dev/null; then
    PI_HOST="pi@10.42.0.1"
    echo "✅ Connected via WiFi hotspot"
elif ping -c 1 -W 2 100.76.232.7 &> /dev/null; then
    PI_HOST="pi@100.76.232.7"
    echo "✅ Connected via Tailscale"
else
    echo "❌ Cannot reach Pi"
    exit 1
fi

echo ""
echo "📤 Copying updated files..."

# Copy Python scripts
scp capture_upload_compressed.py ${PI_HOST}:/home/pi/capture_upload.py
scp gallery.html ${PI_HOST}:/home/pi/gallery.html
scp gallery_server.py ${PI_HOST}:/home/pi/gallery_server.py

# Copy helper scripts
scp keep_modem_awake.sh ${PI_HOST}:/home/pi/keep_modem_awake.sh
ssh ${PI_HOST} "chmod +x /home/pi/keep_modem_awake.sh"

# Copy systemd service files
scp ranch-camera.service ${PI_HOST}:/tmp/ranch-camera.service
scp ranch-camera.timer ${PI_HOST}:/tmp/ranch-camera.timer

echo ""
echo "🔧 Installing systemd services..."

# Install systemd files and reload daemon
ssh ${PI_HOST} "sudo mv /tmp/ranch-camera.service /etc/systemd/system/ && \
               sudo mv /tmp/ranch-camera.timer /etc/systemd/system/ && \
               sudo systemctl daemon-reload && \
               sudo systemctl enable ranch-camera.timer"

echo ""
echo "🔄 Restarting services..."

# Restart gallery server to load new HTML
ssh ${PI_HOST} "sudo systemctl restart gallery-server.service"

# Restart camera timer to load new configuration
ssh ${PI_HOST} "sudo systemctl restart ranch-camera.timer"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📝 Changes applied:"
echo "   - Modem sleep mode: ENABLED (saves ~400mA)"
echo "   - Deep idle mode: ENABLED (saves ~75mA)"
echo "   - Modem wake window: 5 minutes per capture (allows SSH access)"
echo "   - Keep-awake helper: ~/keep_modem_awake.sh"
echo "   - Supabase upload configured (spypoint-images bucket)"
echo "   - Images upload to: tophand-zero-04/YYYY/MM/DD/"
echo ""
echo "⚡ Battery Life Estimate:"
echo "   - With modem sleep + deep idle: ~4-5 days on 12,000mAh battery"
echo "   - With modem sleep only: ~2 days"
echo "   - Without optimizations: ~1.5 days"
echo "   - Power draw: ~1.1W average (was ~2.5W)"
echo ""
echo "🔧 SSH Access During Sleep:"
echo "   - Modem wakes hourly at :01 (e.g., 5:01, 6:01)"
echo "   - 5-minute window to SSH in"
echo "   - Run: bash keep_modem_awake.sh (to extend session)"
echo ""
echo "🧪 Test capture: ssh ${PI_HOST} 'sudo systemctl start ranch-camera.service'"
echo "📊 View logs: ssh ${PI_HOST} 'journalctl -u ranch-camera.service -f'"
