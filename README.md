# SecureUSB

🔒 **TOTP Based USB Device Auth and Management**

SecureUSB protects your computer from unauthorized USB devices by requiring TOTP (Time-based One-Time Password) authentication before any USB device can connect. Perfect for high-security environments, prevents BadUSB attacks, and provides complete audit logging of all USB connections.

## Features

- 🛡️ **USB Port Protection**: All USB ports are blocked by default
- 📱 **TOTP Authentication**: Uses Google Authenticator for device authorization
- ⚡ **Real-time Authorization**: Popup dialog for each device connection
- 🔌 **Power-Only Mode**: Allow device charging while blocking data transfer
- 📋 **Device Whitelisting**: Remember trusted devices (still requires TOTP)
- 📊 **Audit Logging**: Complete history of all USB connection attempts
- 🔐 **Recovery Codes**: Emergency access if you lose your phone
- 🎨 **Native GNOME Integration**: Beautiful GTK4/Libadwaita interface
- 🚀 **Automatic Startup**: Runs automatically on system boot

## Screenshots

### Authorization Dialog
When you plug in a USB device, you'll see this dialog:

```
┌─────────────────────────────────────────────┐
│      ⚠  USB Device Authorization Required   │
├─────────────────────────────────────────────┤
│                                             │
│  Device Information:                        │
│  📱 Logitech USB Receiver                   │
│  🔢 046d:c52b                               │
│  #️⃣  ABC123456                              │
│                                             │
│  Authentication:                            │
│  ┌──────────┐                               │
│  │ 123456   │ ← Enter TOTP code             │
│  └──────────┘                               │
│  Time remaining: 25s                        │
│                                             │
│  ☐ Remember this device                     │
│                                             │
│  [Deny] [Power Only] [Connect]             │
└─────────────────────────────────────────────┘
```

### Setup Wizard
First-time configuration with QR code for Google Authenticator.

## Requirements

- **OS**: Modern Linux distribution with systemd (tested on GNOME-based Debian derivatives)
- **Desktop**: GNOME
- **Python**: 3.13+
- **Privileges**: Root access for installation

### System Dependencies
- python3-gi (PyGObject)
- python3-dbus
- gir1.2-gtk-4.0 (GTK4)
- gir1.2-gtk-3.0 (AppIndicator menu)
- gir1.2-adw-1
- gir1.2-ayatanaappindicator3-0.1 (tray indicator)
- udev
- systemd
- policykit-1

**GNOME Users (3.26+)**: Modern GNOME removed native AppIndicator support. You must install the **AppIndicator extension**:
```bash
# Install via GNOME Extensions website:
# https://extensions.gnome.org/extension/615/appindicator-support/

# Or via package manager (Ubuntu/Debian):
sudo apt install gnome-shell-extension-appindicator

# Then enable it:
gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com
```

### Python Dependencies
- pyudev - USB device monitoring
- pyotp - TOTP authentication
- qrcode - QR code generation
- cryptography - Secure storage
- Pillow - Image processing

## Installation

### Quick Install

```bash
# Clone the repository
git clone https://github.com/yourusername/secureusb.git
cd secureusb

# Run installation script
sudo ./install.sh
```

The installation script will:
1. Install all system and Python dependencies
2. Copy files to `/opt/secureusb`
3. Install systemd service, udev rules, and polkit policy
4. Launch the setup wizard automatically
5. Enable the daemon to start on boot

### Manual Installation

If you prefer to install manually:

```bash
# Install system dependencies
sudo apt update
sudo apt install python3-pip python3-gi python3-dbus \
                 gir1.2-gtk-4.0 gir1.2-adw-1 \
                 udev policykit-1

# Install Python dependencies
pip3 install --break-system-packages pyudev pyotp qrcode[pil] cryptography pillow

# Copy files
sudo mkdir -p /opt/secureusb
sudo cp -r src /opt/secureusb/
sudo cp data/udev/99-secureusb.rules /etc/udev/rules.d/
sudo cp data/systemd/secureusb.service /etc/systemd/system/
sudo cp data/polkit/org.secureusb.policy /usr/share/polkit-1/actions/
sudo cp data/dbus/org.secureusb.Daemon.conf /etc/dbus-1/system.d/

# Reload services
sudo udevadm control --reload-rules
sudo systemctl daemon-reload

# Enable and start daemon
sudo systemctl enable secureusb
sudo systemctl start secureusb

# Run setup wizard
python3 /opt/secureusb/src/gui/setup_wizard.py
```

## Setup

### First-Time Configuration

1. **Run Setup Wizard**:
   ```bash
   secureusb-setup
   ```

2. **Install Google Authenticator**:
   - Download from [Google Play](https://play.google.com/store/apps/details?id=com.google.android.apps.authenticator2) or [App Store](https://apps.apple.com/app/google-authenticator/id388497605)

3. **Scan QR Code**:
   - Open Google Authenticator
   - Tap "+" → "Scan QR code"
   - Scan the QR code shown in the wizard

4. **Save Recovery Codes**:
   - Write down or print the 10 recovery codes
   - Store them in a secure location
   - You can use these if you lose your phone

5. **Test Authentication**:
   - Enter the 6-digit code from your app
   - If correct, setup is complete!

### Configuration Files

SecureUSB stores its configuration in `/var/lib/secureusb/` (created during installation):
- `/var/lib/secureusb/auth.enc` - Encrypted TOTP secret and recovery codes
- `/var/lib/secureusb/config.json` - Application settings
- `/var/lib/secureusb/whitelist.json` - Whitelisted devices
- `/var/lib/secureusb/events.db` - SQLite database of USB events
  - If you installed a previous version, the installer migrates data from `~/.config/secureusb` automatically.

## Usage

### Daily Use

1. **Plug in USB Device**:
   - Authorization dialog appears automatically
   - Shows device information

2. **Enter TOTP Code**:
   - Open Google Authenticator on your phone
   - Enter the 6-digit code for SecureUSB
   - Code changes every 30 seconds

3. **Choose Action**:
   - **Connect**: Full data and power access
   - **Power Only**: Charging only, no data transfer
   - **Deny**: Block the device completely

4. **Optional**: Check "Remember this device"
   - Device will be whitelisted
   - Still requires TOTP, but shows simplified dialog

### Commands

```bash
# Check daemon status
sudo systemctl status secureusb

# Restart daemon
sudo systemctl restart secureusb

# Stop daemon (allows all USB devices)
sudo systemctl stop secureusb

# View daemon logs
sudo journalctl -u secureusb -f

# Run setup wizard again
secureusb-setup

# Start GUI client manually
secureusb-client

# Restart the tray indicator
secureusb-indicator &
```

### Configuration

Edit `/var/lib/secureusb/config.json`:

```json
{
  "general": {
    "enabled": true,
    "auto_start": true,
    "timeout_seconds": 30,
    "default_action": "deny"
  },
  "notifications": {
    "enabled": true,
    "sound": false,
    "show_on_deny": true
  },
  "security": {
    "require_totp_for_whitelisted": true,
    "log_retention_days": 90
  }
}
```

## Security Features

### USB Authorization
- Uses Linux kernel's USB authorization framework (`/sys/bus/usb/devices/*/authorized`)
- Blocks devices at kernel level before driver initialization
- Prevents BadUSB and malicious firmware attacks

### Authentication
- **TOTP (RFC 6238)**: Industry-standard time-based one-time passwords
- **Google Authenticator**: Compatible with all TOTP apps
- **Recovery Codes**: 10 one-time use backup codes
- **Code Reuse Prevention**: Same code can't be used twice in 30-second window

### Encryption
- TOTP secrets encrypted with AES-256
- Key derived from machine-specific data (machine-id)
- PBKDF2 with 100,000 iterations
- Recovery codes stored as SHA-256 hashes

### Audit Trail
- All USB connection attempts logged to SQLite database
- Records: timestamp, device info, action, auth status
- Configurable retention period
- Export to CSV for analysis

### System Integration
- **Polkit**: Controlled privilege escalation
- **D-Bus**: Secure daemon ↔ GUI communication
- **systemd**: Proper service management and hardening
- **udev**: Early device detection

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    User Space                       │
│                                                     │
│  ┌──────────────┐      ┌──────────────────────┐  │
│  │ GTK4 GUI     │◄────►│ GNOME Shell          │  │
│  │ - Auth Dialog│      │ - Notifications      │  │
│  │ - Setup Wizard│     │                      │  │
│  └──────┬───────┘      └──────────────────────┘  │
│         │                                          │
│         │ D-Bus (org.secureusb.Daemon)            │
│         │                                          │
├─────────┼──────────────────────────────────────────┤
│         │              Root Daemon                 │
│         ▼                                          │
│  ┌──────────────────────────────────────────┐    │
│  │ SecureUSB Daemon (root)                  │    │
│  │                                          │    │
│  │ ┌────────────┐  ┌─────────────────────┐ │    │
│  │ │ USB Monitor│  │ Authorization Engine│ │    │
│  │ │  (pyudev)  │  │   - TOTP Verify     │ │    │
│  │ └─────┬──────┘  │   - Whitelist Check │ │    │
│  │       │         │   - Logging         │ │    │
│  │       │         └─────────┬───────────┘ │    │
│  └───────┼───────────────────┼─────────────┘    │
│          │                   │                   │
├──────────┼───────────────────┼───────────────────┤
│          │   Kernel Space    │                   │
│          │                   │                   │
│          ▼                   ▼                   │
│   ┌────────────┐      ┌────────────┐           │
│   │ udev events│      │  sysfs     │           │
│   │            │      │ authorized │           │
│   └────────────┘      └────────────┘           │
└─────────────────────────────────────────────────┘
```

### Components

1. **Daemon** (`src/daemon/`):
   - `service.py` - Main daemon service
   - `usb_monitor.py` - USB device monitoring (pyudev)
   - `authorization.py` - Kernel-level USB control
   - `dbus_service.py` - D-Bus interface

2. **GUI** (`src/gui/`):
   - `client.py` - Main client application
   - `auth_dialog.py` - Authorization popup
   - `setup_wizard.py` - First-time setup

3. **Authentication** (`src/auth/`):
   - `totp.py` - TOTP generation and verification
   - `storage.py` - Encrypted credential storage

4. **Utilities** (`src/utils/`):
   - `logger.py` - SQLite event logging
   - `config.py` - Configuration management
   - `whitelist.py` - Device whitelist management

### Platform Ports

- **Linux**: Full daemon + GTK workflow (default `install.sh`).
- **Windows 11** (`windows/`): PySide6 desktop agent that relies on `pnputil`
  to disable/enable USB devices. See `windows/README.md` for setup details.
- **macOS 12+** (`macos/`): PySide6 UI with IOKit integration and optional
  launchd service. See `macos/README.md`.

### Native Packages

Packaging scripts for `.pkg`, `.msi`, and `.deb` installers live under
`packaging/`. See `packaging/README.md` for build instructions.

## Troubleshooting

### Daemon Won't Start

```bash
# Check status
sudo systemctl status secureusb

# View logs
sudo journalctl -u secureusb -n 50

# Common issues:
# - TOTP not configured: Run secureusb-setup
# - Permission error: Check /opt/secureusb ownership
# - Python dependencies: Reinstall with pip3
```

### Tray Icon Not Showing in GNOME Top Bar

**Cause**: Modern GNOME (3.26+) removed native AppIndicator support.

**Solution**: Install the AppIndicator GNOME Shell extension:

```bash
# Method 1: Via package manager (Ubuntu/Debian)
sudo apt install gnome-shell-extension-appindicator

# Method 2: Via GNOME Extensions website
# Visit: https://extensions.gnome.org/extension/615/appindicator-support/
# Click "Install" and follow browser prompts

# Enable the extension:
gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com

# Restart GNOME Shell:
# Press Alt+F2, type 'r', press Enter
# (Or log out and log back in)
```

**Verify indicator is running**:
```bash
ps aux | grep indicator.py
# Should show: /usr/bin/python3 /opt/secureusb/src/gui/indicator.py

# Check if extension is enabled:
gnome-extensions list --enabled | grep appindicator
```

### Authorization Dialog Not Appearing

```bash
# Check if client is running
ps aux | grep "client.py"

# Start client manually
secureusb-client

# Check autostart files
ls ~/.config/autostart/secureusb-*.desktop
```

### Device Not Blocked

```bash
# Check if daemon is running
sudo systemctl status secureusb

# Check USB authorization default
cat /sys/bus/usb/devices/usb*/authorized_default
# Should show "0" (blocked)

# Manually set to block
echo 0 | sudo tee /sys/bus/usb/devices/usb*/authorized_default
```

### Lost Phone / Can't Access TOTP

Use recovery codes:
1. Enter recovery code instead of TOTP code in authorization dialog
2. Recovery codes are one-time use
3. If you've lost recovery codes, you'll need to:
   ```bash
   # Remove configuration
   rm -rf /var/lib/secureusb

   # Run setup wizard again
   secureusb-setup
   ```

### View Event Logs

```python
# Using Python
from src.utils import USBLogger

logger = USBLogger()
events = logger.get_recent_events(limit=50)

for event in events:
    print(f"{event['timestamp']}: {event['action']} - {event['product_name']}")
```

## Uninstallation

```bash
# Run uninstall script
sudo ./uninstall.sh
```

This will:
- Stop and disable the daemon
- Remove all system files
- Ask if you want to remove user configuration
- Re-enable USB authorization (devices will work normally)

## Development

### Project Structure

```
secureusb/
├── src/
│   ├── daemon/          # Background service (root)
│   ├── gui/             # GTK4 user interface
│   ├── auth/            # TOTP authentication
│   └── utils/           # Logging, config, whitelist
├── data/
│   ├── udev/            # udev rules
│   ├── systemd/         # systemd service
│   ├── polkit/          # polkit policy
│   ├── dbus/            # D-Bus configuration
│   └── desktop/         # autostart entries
├── tests/               # Unit tests
├── docs/                # Documentation
├── macos/               # macOS port + pkg builder
├── windows/             # Windows port + MSI builder
├── packaging/           # Cross-platform packaging scripts
├── install.sh           # Installation script
├── uninstall.sh         # Uninstallation script
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

### Running Tests

```bash
cd secureusb

# Test TOTP module
python3 src/auth/totp.py

# Test secure storage
python3 src/auth/storage.py

# Test USB monitor
sudo python3 src/daemon/usb_monitor.py

# Test authorization
sudo python3 src/daemon/authorization.py
```

### Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## FAQ

**Q: Does this work on other Linux distributions?**
A: It should work on most modern systemd-based GNOME distributions (Debian, Fedora, Arch, etc.). Other environments may require tweaks to the service files.

**Q: Can I use a different TOTP app?**
A: Yes! Any TOTP app (Authy, Microsoft Authenticator, etc.) that supports RFC 6238 will work.

**Q: What if I need to use a USB device in an emergency?**
A: Use a recovery code, or boot into single-user mode and disable the service.

**Q: Does this affect internal USB devices (keyboard, mouse)?**
A: No. The system detects devices connected before the daemon starts and allows them. Only new devices after boot require authorization.

**Q: How secure is this against advanced attacks?**
A: SecureUSB provides strong protection against most USB attacks (BadUSB, malicious firmware). However, it cannot protect against:
- Physical tampering with internal USB headers
- DMA attacks via Thunderbolt (use Thunderbolt security features)
- Attacks before the kernel initializes

**Q: Performance impact?**
A: Minimal. The daemon uses ~20MB RAM and negligible CPU. USB device detection adds <1ms latency.

## License

The community edition is provided under the MIT License (see `LICENSE`). Commercial deployments, OEM bundles, or hosted services must obtain a commercial license by accepting the SecureUSB EULA (see `EULA.md`).

## Author

Created for GNOME desktop environments on modern Linux distributions.

## Support

- General inquiries & licensing: hello@othertales.co | +1 302 405 8005
- Security issues: hello@othertales.co (use subject "SecureUSB Security")
- Report bugs: https://github.com/yourusername/secureusb/issues

## Acknowledgments

- Linux kernel USB authorization framework
- pyudev for USB monitoring
- PyOTP for TOTP implementation
- GTK/GNOME teams for beautiful UI toolkit
