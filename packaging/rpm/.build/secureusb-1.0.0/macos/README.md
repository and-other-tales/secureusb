# SecureUSB for macOS

macOS port of SecureUSB - TOTP-based USB device authentication and management.

## Overview

The macOS version of SecureUSB provides USB device protection using macOS IOKit framework instead of Linux's kernel authorization framework. It uses PySide6 for the GUI instead of GTK4.

## System Requirements

- **OS**: macOS 12 (Monterey) or later
- **Architecture**: x86_64 (Intel) or arm64 (Apple Silicon)
- **Python**: 3.9 or later (included with macOS)
- **Administrator privileges**: Required for device management and daemon installation

## Installation

### Option 1: PKG Installer (Recommended)

1. Download `SecureUSB-x.x.x.pkg` from releases
2. Double-click the PKG file
3. Follow the installation wizard
4. Run setup in Terminal:
   ```bash
   sudo secureusb-macos setup
   ```
5. Scan the QR code with Google Authenticator
6. Save your recovery codes

### Option 2: Manual Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/secureusb.git
cd secureusb

# Install Python dependencies
pip3 install -r macos/requirements.txt

# Run setup wizard
python3 ports/shared/setup_cli.py
```

## Building the PKG

### Prerequisites

1. **Xcode Command Line Tools**:
   ```bash
   xcode-select --install
   ```

2. **Python 3.9+**: Built into macOS (check with `python3 --version`)

3. **Build tools**: `pkgbuild`, `productbuild` (included in Xcode CLI Tools)

### Build Steps

```bash
# Navigate to the pkg build directory
cd macos/pkg

# Run the build script
./build_pkg.sh 1.0.0

# Output will be in macos/pkg/dist/
```

The build script will:
1. Validate all dependencies are available
2. Copy application files to payload directory
3. Set proper permissions
4. Build the component package with scripts
5. Create the final product package with installer UI

### Build Options

```bash
# Build with a specific version
./build_pkg.sh 2.0.0

# The script will automatically:
# - Clean previous builds
# - Copy source files (src/, data/, ports/, macos/)
# - Include documentation (README.md, LICENSE, EULA.md)
# - Set up installation scripts
# - Create installer resources
```

### Signing the Package

For distribution outside the App Store, sign the package with your Developer ID:

```bash
# Sign the package
productsign --sign "Developer ID Installer: Your Name (TEAM_ID)" \
  "macos/pkg/dist/SecureUSB-1.0.0.pkg" \
  "macos/pkg/dist/SecureUSB-1.0.0-signed.pkg"

# Verify the signature
pkgutil --check-signature "macos/pkg/dist/SecureUSB-1.0.0-signed.pkg"

# Notarize with Apple (required for macOS 10.15+)
xcrun notarytool submit "macos/pkg/dist/SecureUSB-1.0.0-signed.pkg" \
  --apple-id "your-email@example.com" \
  --team-id "TEAM_ID" \
  --password "app-specific-password"
```

## Architecture Differences from Linux

### Device Management

| Feature | Linux | macOS |
|---------|-------|-------|
| **Device Detection** | udev + pyudev | IOKit + pyobjc |
| **Device Control** | sysfs `/sys/bus/usb/devices/*/authorized` | IOKit device matching & blocking |
| **Service Management** | systemd | LaunchDaemon |
| **Privilege Escalation** | polkit | Authorization Services |
| **IPC** | D-Bus | XPC / Distributed Objects |

### GUI Framework

- **Linux**: GTK4 + Libadwaita (GNOME native)
- **macOS**: PySide6 (Qt6) for cross-platform compatibility

### File Locations

| Component | Linux | macOS |
|-----------|-------|-------|
| **Installation** | `/opt/secureusb` | `/opt/secureusb` |
| **Configuration** | `/var/lib/secureusb` | `/Library/Application Support/SecureUSB` |
| **User Data** | `~/.config/secureusb` (legacy) | `~/Library/Application Support/SecureUSB` |
| **Logs** | `/var/log/secureusb` or journalctl | `/Library/Logs/SecureUSB` |
| **LaunchDaemon** | N/A | `/Library/LaunchDaemons/org.secureusb.daemon.plist` |

## Usage

### First-Time Setup

1. Open Terminal (Applications → Utilities → Terminal)
2. Run the setup wizard:
   ```bash
   sudo secureusb-macos setup
   ```
3. Install Google Authenticator on your phone
4. Scan the QR code shown in Terminal
5. Save your 10 recovery codes
6. Enter a TOTP code to verify

### Daily Use

1. Plug in a USB device
2. A popup will appear requesting TOTP code
3. Open Google Authenticator
4. Enter the 6-digit code
5. Choose: Connect, Power Only, or Deny

### Commands

```bash
# Main command wrapper
secureusb-macos <command>

# Available commands:
secureusb-macos setup       # Run initial setup wizard
secureusb-macos start       # Start the daemon service
secureusb-macos stop        # Stop the daemon service
secureusb-macos restart     # Restart the daemon service
secureusb-macos status      # Check if daemon is running
secureusb-macos daemon      # Run daemon manually (debugging)
secureusb-macos client      # Run GUI client manually
secureusb-macos help        # Show help message

# Individual component commands:
secureusb-setup            # Setup wizard only
secureusb-daemon           # Daemon only
secureusb-client           # Client only

# Check LaunchDaemon status
sudo launchctl list | grep secureusb

# View daemon logs
tail -f /Library/Logs/SecureUSB/daemon.log

# Manually load/unload LaunchDaemon
sudo launchctl load /Library/LaunchDaemons/org.secureusb.daemon.plist
sudo launchctl unload /Library/LaunchDaemons/org.secureusb.daemon.plist
```

## macOS-Specific Features

### IOKit Integration

SecureUSB on macOS uses IOKit to:
- Monitor USB device attachment events
- Query device properties (VID, PID, serial number)
- Block devices at the IOKit layer
- Prevent driver attachment for unauthorized devices

### LaunchDaemon Service

The daemon runs as a LaunchDaemon (system service) which:
- Starts automatically at boot
- Runs with root privileges
- Restarts automatically if it crashes
- Logs to `/Library/Logs/SecureUSB/`

### System Integrity Protection (SIP)

SecureUSB works with SIP enabled. It doesn't require any kernel extensions (kexts) or system modifications.

## Limitations on macOS

1. **Driver loading timing**: macOS may briefly load drivers before SecureUSB can block them. Use fast TOTP authentication.

2. **Built-in devices**: Internal USB controllers (keyboard, trackpad, Touch ID) cannot be blocked.

3. **Thunderbolt devices**: Thunderbolt devices have separate security settings in System Preferences → Security & Privacy.

4. **FileVault**: USB authentication may not work during FileVault unlock screen. Configure trusted devices appropriately.

5. **Recovery Mode**: SecureUSB doesn't run in Recovery Mode. All USB devices work normally in Recovery.

## Security Considerations

### IOKit-Based Control

Unlike Linux's kernel-level authorization, macOS uses IOKit-level control:
- **Advantage**: No kernel modifications required; SIP compatible
- **Disadvantage**: Brief window between device attachment and blocking
- **Mitigation**: SecureUSB registers for immediate IOKit notifications

### Sandboxing and Hardening

The LaunchDaemon runs with:
- Minimal privileges (only what's needed for USB control)
- Automatic restart on failure
- Logging enabled for audit trail
- No network access required

## Package Structure

```
macos/
├── pkg/                           # PKG installer build files
│   ├── build_pkg.sh              # Main build script
│   ├── distribution-template.xml # Installer configuration
│   ├── scripts/
│   │   ├── preinstall            # Pre-installation cleanup
│   │   └── postinstall           # Post-installation setup
│   ├── Resources/                # Installer UI resources
│   │   ├── welcome.html          # Welcome screen
│   │   ├── conclusion.html       # Completion screen
│   │   └── LICENSE.txt           # License (copied from root)
│   └── dist/                     # Build output directory
├── requirements.txt              # macOS-specific dependencies
├── org.secureusb.daemon.plist    # LaunchDaemon configuration
└── README.md                     # This file
```

## Troubleshooting

### PKG Build Fails

**Problem**: `pkgbuild: command not found`
```bash
# Solution: Install Xcode Command Line Tools
xcode-select --install
```

**Problem**: `Permission denied` when building
```bash
# Solution: Ensure scripts are executable
chmod +x macos/pkg/build_pkg.sh
chmod +x macos/pkg/scripts/*
```

### Installation Issues

**Problem**: Package won't install (unsigned)
```bash
# Solution: Allow installation from unidentified developers temporarily
# System Preferences → Security & Privacy → General
# Or use command line:
sudo installer -pkg SecureUSB-1.0.0.pkg -target / -allowUntrusted
```

**Problem**: `pip3: command not found`
```bash
# Solution: Install Python 3 via Homebrew
brew install python3

# Or use macOS built-in Python 3
python3 -m ensurepip
```

### Daemon Won't Start

```bash
# Check LaunchDaemon status
sudo launchctl list | grep org.secureusb.daemon

# View error logs
cat /Library/Logs/SecureUSB/daemon.error.log

# Manually load the daemon with verbose output
sudo launchctl load -w /Library/LaunchDaemons/org.secureusb.daemon.plist

# Check Python dependencies
pip3 list | grep -E "pyotp|qrcode|cryptography|pyobjc|PySide6"
```

### Device Not Blocked

1. **Check if daemon is running**:
   ```bash
   secureusb-macos status
   # or
   ps aux | grep "secureusb"
   ```

2. **Verify IOKit permissions**:
   ```bash
   # The daemon needs to run as root
   sudo secureusb-macos restart
   ```

3. **Check device in System Information**:
   - Apple Menu → About This Mac → System Report → USB
   - Verify the device appears in the list

### Authorization Dialog Not Appearing

1. **Check if client is running**:
   ```bash
   ps aux | grep "client.py"
   ```

2. **Start client manually**:
   ```bash
   secureusb-client
   ```

3. **Check GUI framework**:
   ```bash
   python3 -c "from PySide6 import QtWidgets; print('PySide6 OK')"
   ```

## Uninstallation

### Using the Uninstall Script

```bash
# Create an uninstall script
sudo bash <<'EOF'
# Stop and remove LaunchDaemon
launchctl unload /Library/LaunchDaemons/org.secureusb.daemon.plist 2>/dev/null
rm -f /Library/LaunchDaemons/org.secureusb.daemon.plist

# Remove application files
rm -rf /opt/secureusb

# Remove wrapper scripts
rm -f /usr/local/bin/secureusb-*

# Optionally remove configuration (comment out to keep settings)
# rm -rf "/Library/Application Support/SecureUSB"
# rm -rf "/Library/Logs/SecureUSB"

echo "SecureUSB uninstalled successfully"
EOF
```

### Manual Uninstallation

```bash
# 1. Stop the daemon
sudo launchctl unload /Library/LaunchDaemons/org.secureusb.daemon.plist

# 2. Remove LaunchDaemon plist
sudo rm /Library/LaunchDaemons/org.secureusb.daemon.plist

# 3. Remove application
sudo rm -rf /opt/secureusb

# 4. Remove wrapper scripts
sudo rm -f /usr/local/bin/secureusb-*

# 5. (Optional) Remove configuration
sudo rm -rf "/Library/Application Support/SecureUSB"
sudo rm -rf "/Library/Logs/SecureUSB"
```

## Development

### Testing the Build

```bash
# Build the package
cd macos/pkg
./build_pkg.sh 1.0.0

# Test installation in a VM or test machine
sudo installer -pkg dist/SecureUSB-1.0.0.pkg -target / -verbose

# Check installation
ls -la /opt/secureusb
ls -la /Library/LaunchDaemons/org.secureusb.daemon.plist
which secureusb-macos

# Test the commands
secureusb-macos status
sudo secureusb-macos setup
```

### Testing Individual Components

```bash
# Test TOTP module
python3 -c "from src.auth.totp import TOTPAuthenticator; print('OK')"

# Test IOKit device enumeration
python3 -c "from Foundation import *; from IOKit import *; print('IOKit OK')"

# Test secure storage
python3 src/auth/storage.py

# Test daemon (requires root)
sudo python3 src/daemon/service.py
```

## Contributing

Contributions to the macOS port are welcome! Please:
1. Test on both Intel and Apple Silicon Macs
2. Ensure compatibility with macOS 12 (Monterey) and later
3. Follow Apple's Human Interface Guidelines for UI
4. Update this README with any new features

## License

MIT License (see LICENSE file in repository root)

For commercial deployments, see EULA.md

## Support

- General inquiries: hello@othertales.co
- Security issues: hello@othertales.co (subject: "SecureUSB Security")
- Bug reports: https://github.com/yourusername/secureusb/issues

## Acknowledgments

- Apple IOKit framework for USB device management
- PyObjC for Python-Objective-C bridge
- PySide6 for cross-platform GUI
- PyOTP for TOTP implementation
