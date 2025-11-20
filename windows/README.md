# SecureUSB for Windows

Windows port of SecureUSB - TOTP-based USB device authentication and management.

## Overview

The Windows version of SecureUSB provides USB device protection using Windows Device Manager APIs instead of Linux's kernel authorization framework. It uses PySide6 for the GUI instead of GTK4.

## System Requirements

- **OS**: Windows 10 (version 1809+) or Windows 11
- **Architecture**: x64 (64-bit)
- **Python**: 3.11 or higher
- **Administrator privileges**: Required for device management

## Installation

### Option 1: MSI Installer (Recommended)

1. Download `SecureUSB-x.x.x-x64.msi` from releases
2. Double-click the MSI file
3. Follow the installation wizard
4. Run "SecureUSB Setup" from the Start Menu
5. Scan the QR code with Google Authenticator
6. Save your recovery codes

### Option 2: Manual Installation

```powershell
# Clone the repository
git clone https://github.com/yourusername/secureusb.git
cd secureusb

# Install Python dependencies
pip install -r windows/requirements.txt

# Run setup wizard
python ports/shared/setup_cli.py
```

## Building the MSI

### Prerequisites

1. **WiX Toolset v3.11+**: Download from https://wixtoolset.org/releases/
2. **Python 3.11+**: Ensure Python is in your PATH
3. **PowerShell 5.1+**: Built into Windows 10/11

### Build Steps

```powershell
# Navigate to the MSI build directory
cd windows/msi

# Run the build script
.\build_msi.ps1 -Version 1.0.0

# Output will be in windows/msi/dist/
```

The build script will:
1. Locate WiX Toolset automatically
2. Harvest all application files
3. Compile WiX source files
4. Link the final MSI package

### Build Options

```powershell
# Specify a custom WiX path
.\build_msi.ps1 -Version 1.0.0 -WixPath "C:\WiX\bin"

# Build with a different version
.\build_msi.ps1 -Version 2.0.0
```

## Architecture Differences from Linux

### Device Management

| Feature | Linux | Windows |
|---------|-------|---------|
| **Device Detection** | udev + pyudev | WMI + Windows Device Events |
| **Device Control** | sysfs `/sys/bus/usb/devices/*/authorized` | Device Manager API (`pnputil`, registry) |
| **Service Management** | systemd | Windows Service / Task Scheduler |
| **Privilege Escalation** | polkit | UAC / Administrator |
| **IPC** | D-Bus | Named Pipes / COM |

### GUI Framework

- **Linux**: GTK4 + Libadwaita (GNOME native)
- **Windows**: PySide6 (Qt6) for cross-platform compatibility

### File Locations

| Component | Linux | Windows |
|-----------|-------|---------|
| **Installation** | `/opt/secureusb` | `C:\Program Files\SecureUSB` |
| **Configuration** | `/var/lib/secureusb` | `%ProgramData%\SecureUSB` |
| **User Data** | `~/.config/secureusb` (legacy) | `%APPDATA%\SecureUSB` |
| **Logs** | `/var/log/secureusb` or journalctl | `%ProgramData%\SecureUSB\logs` |

## Usage

### First-Time Setup

1. Run "SecureUSB Setup" from Start Menu
2. Install Google Authenticator on your phone
3. Scan the QR code shown
4. Save your 10 recovery codes
5. Test authentication

### Daily Use

1. Plug in a USB device
2. A popup will appear requesting TOTP code
3. Open Google Authenticator
4. Enter the 6-digit code
5. Choose: Connect, Power Only, or Deny

### Commands

```powershell
# Run setup wizard
secureusb-setup

# Start the daemon manually
secureusb-daemon

# Start the GUI client
secureusb-client

# Check device status
Get-PnpDevice -Class USB | Where-Object Status -eq "Error"
```

## Windows-Specific Features

### Device Management via Device Manager

SecureUSB on Windows uses the Windows Device Manager API to:
- Detect USB device insertion events
- Disable/enable devices programmatically
- Query device properties (VID, PID, serial number)
- Prevent driver installation for unauthorized devices

### Power Management

Windows supports "charging only" mode through:
- Disabling the USB device driver
- Keeping power pins active
- Blocking data transfer at the driver level

## Limitations on Windows

1. **Kernel-level blocking**: Windows doesn't support the same kernel-level USB authorization as Linux. Devices briefly initialize before being disabled.
2. **Driver delays**: Some devices may start initializing before SecureUSB can block them (requires fast authentication).
3. **Admin rights**: Windows requires administrator privileges for device management.
4. **USB controllers**: Built-in USB controllers (keyboard, mouse) cannot be blocked.

## Security Considerations

### Windows Device Manager Approach

Unlike Linux's kernel-level authorization, Windows uses driver-level control:
- **Advantage**: Works on all Windows versions without kernel modifications
- **Disadvantage**: Small window between device insertion and driver loading
- **Mitigation**: SecureUSB registers for device arrival events and acts within milliseconds

### UAC and Privileges

The SecureUSB daemon requires administrator privileges to:
- Manage device drivers
- Modify device registry entries
- Monitor system-level events

The installer sets up the service to run with appropriate privileges.

## Troubleshooting

### MSI Build Fails

**Problem**: `WiX Toolset not found`
```powershell
# Solution: Install WiX Toolset or specify path
.\build_msi.ps1 -WixPath "C:\Program Files (x86)\WiX Toolset v3.11\bin"
```

**Problem**: `Compilation failed`
- Check that all source files exist
- Ensure Python dependencies are installed
- Review build output for specific errors

### Device Not Blocked

1. **Check if daemon is running**:
   ```powershell
   Get-Process | Where-Object {$_.ProcessName -like "*secureusb*"}
   ```

2. **Run as Administrator**:
   - Right-click `secureusb-daemon.bat`
   - Select "Run as administrator"

3. **Check device status**:
   ```powershell
   Get-PnpDevice -Class USB
   ```

### Authorization Dialog Not Appearing

1. **Check if client is running**:
   ```powershell
   Get-Process | Where-Object {$_.ProcessName -like "*python*"}
   ```

2. **Start client manually**:
   ```powershell
   secureusb-client
   ```

3. **Check firewall**: Ensure Windows Firewall isn't blocking inter-process communication

## Development

### Project Structure

```
windows/
├── msi/                    # MSI installer build files
│   ├── Product.wxs         # Main WiX configuration
│   ├── build_msi.ps1       # Build script
│   ├── License.rtf         # License for installer
│   ├── secureusb-setup.bat # Setup launcher
│   ├── secureusb-daemon.bat# Daemon launcher
│   └── secureusb-client.bat# Client launcher
├── requirements.txt        # Windows-specific dependencies
└── README.md              # This file
```

### Testing

```powershell
# Test setup wizard
python ports\shared\setup_cli.py

# Test TOTP authentication
python -c "from src.auth.totp import TOTPAuthenticator; print(TOTPAuthenticator.generate_secret())"

# Test device detection (requires admin)
python -c "import wmi; c = wmi.WMI(); print([d.Caption for d in c.Win32_PnPEntity() if 'USB' in d.Caption])"
```

### Building from Source

1. Install build dependencies:
   ```powershell
   pip install -r windows/requirements.txt
   ```

2. Build the MSI:
   ```powershell
   cd windows/msi
   .\build_msi.ps1 -Version 1.0.0
   ```

3. Test the installer:
   ```powershell
   msiexec /i dist\SecureUSB-1.0.0-x64.msi /l*v install.log
   ```

## Contributing

Contributions to the Windows port are welcome! Please:
1. Test on Windows 10 and Windows 11
2. Ensure compatibility with both Python 3.11 and 3.12
3. Follow the existing code style
4. Update this README with any new features

## License

MIT License (see LICENSE file in repository root)

For commercial deployments, see EULA.md

## Support

- General inquiries: hello@othertales.co
- Security issues: hello@othertales.co (subject: "SecureUSB Security")
- Bug reports: https://github.com/yourusername/secureusb/issues

## Acknowledgments

- WiX Toolset for MSI packaging
- PySide6 for cross-platform GUI
- Windows WMI for device management
