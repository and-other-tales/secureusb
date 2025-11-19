#!/bin/bash
#
# Installer helper for SecureUSB macOS port.
#

set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REQUIREMENTS_FILE="$REPO_ROOT/macos/requirements.txt"
APP_SCRIPT="$REPO_ROOT/macos/src/app.py"
CONFIG_DIR="/Library/Application Support/SecureUSB"
POINTER_FILE="$CONFIG_DIR/config_dir"
LAUNCH_AGENT="/Library/LaunchDaemons/org.secureusb.agent.plist"

if [[ $EUID -ne 0 ]]; then
    echo "This installer must be run as root (sudo macos/install.sh)"
    exit 1
fi

echo "== SecureUSB macOS installer =="
echo "Repo: $REPO_ROOT"
echo "Python: $PYTHON_BIN"

echo ""
echo "Installing Python requirements..."
"$PYTHON_BIN" -m pip install -r "$REQUIREMENTS_FILE"

echo "Ensuring shared configuration directory exists at '$CONFIG_DIR'"
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"
echo "$CONFIG_DIR" > "$POINTER_FILE"

read -p "Install launchd daemon for background execution? (y/N) " -r choice
if [[ $choice =~ ^[Yy]$ ]]; then
    cat > "$LAUNCH_AGENT" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>org.secureusb.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>$APP_SCRIPT</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/secureusb.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/secureusb.err</string>
</dict>
</plist>
EOF
    chmod 644 "$LAUNCH_AGENT"
    launchctl unload "$LAUNCH_AGENT" 2>/dev/null || true
    launchctl load "$LAUNCH_AGENT"
    echo "Launch daemon installed: $LAUNCH_AGENT"
else
    echo "Skipping launchd installation. Start manually with:"
    echo "  sudo $PYTHON_BIN $APP_SCRIPT"
fi

echo ""
echo "Next steps:"
echo "1. Run 'python3 macos/src/setup_cli.py' to configure TOTP."
echo "2. Plug in a USB device to verify the authorization dialog appears."
