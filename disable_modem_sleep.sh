#!/bin/bash
# Script to disable modem sleep and keep modem awake for troubleshooting
# Run this when you can SSH into the Pi

echo "🔧 Disabling modem sleep for troubleshooting..."

# Keep modem awake immediately
touch /tmp/keep_modem_awake
echo "✓ Keep-awake flag set"

# Add passwordless sudo for nmcli (fixes permission issue)
sudo bash -c 'echo "pi ALL=(ALL) NOPASSWD: /usr/bin/nmcli" > /etc/sudoers.d/pi-network'
sudo chmod 0440 /etc/sudoers.d/pi-network
echo "✓ Passwordless sudo configured for nmcli"

# Download and install updated service file (modem sleep disabled)
cd /tmp
wget https://raw.githubusercontent.com/etzlertech/balena-pi-camera/main/ranch-camera.service
sudo mv ranch-camera.service /etc/systemd/system/
sudo systemctl daemon-reload
echo "✓ Service file updated (modem sleep disabled)"

# Check modem status
echo ""
echo "📡 Current modem status:"
nmcli connection show --active | grep -E '(hologram|NAME)'

echo ""
echo "✅ Modem sleep disabled! Modem will stay awake now."
echo ""
echo "To test capture and upload:"
echo "  sudo systemctl start ranch-camera.service"
echo "  journalctl -u ranch-camera.service -f"
