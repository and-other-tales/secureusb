# SecureUSB Packaging

This directory contains helper scripts for producing native installers for each
platform:

- **macOS `.pkg`** – creates a signed-ready installer that copies SecureUSB into
  `/opt/secureusb`, installs a LaunchDaemon, ensures dependencies are installed,
  and prepares the shared config directory.
- **Windows `.msi`** – uses the WiX Toolset to install the SecureUSB port under
  `%ProgramFiles%\SecureUSB`, add Start Menu entries, and drop helper scripts.
- **Debian `.deb`** – builds a dpkg archive that installs SecureUSB into
  `/opt/secureusb`, registers the systemd unit/udev rules/polkit policy,
  and prepares the GNOME indicator autostart entry.

All packaging scripts assume they are executed from the repository root.

## macOS (`macos/pkg/build_pkg.sh`)

Requirements:

- Xcode command-line tools (`pkgbuild`, `productbuild`)
- Python 3 (system default is used for dependency installation)

Usage:

```bash
./macos/pkg/build_pkg.sh 1.0.0
# Outputs: macos/pkg/dist/SecureUSB-1.0.0.pkg
```

The resulting package:

- Installs the repo to `/opt/secureusb`
- Installs `/Library/LaunchDaemons/org.secureusb.agent.plist`
- Creates wrappers under `/usr/local/bin` (`secureusb-setup`, `secureusb-macos`)
- Runs `pip install -r macos/requirements.txt` during `postinstall`
- Initializes `/Library/Application Support/SecureUSB`

## Windows (`windows/msi/build_msi.ps1`)

Requirements:

- Windows 11 with PowerShell 5+
- WiX Toolset (`candle.exe`, `light.exe`) in `PATH`
- Python 3 (`py` launcher or `python`)

Usage (PowerShell):

```powershell
pwsh windows/msi/build_msi.ps1 -Version 1.0.0
# Outputs: windows/msi/dist/SecureUSB-1.0.0.msi
```

Features:

- Installs files under `%ProgramFiles%\SecureUSB`
- Adds Start Menu shortcuts for setup and the USB monitor
- Registers wrappers (`secureusb-windows.ps1`) in `%ProgramFiles%\SecureUSB`
- Runs `pip install -r windows/requirements.txt` on install

## Debian-based distros (`packaging/debian/build_deb.sh`)

Requirements:

- Debian-based distro with `dpkg-deb`, `fakeroot`, and `python3`

Usage:

```bash
./packaging/debian/build_deb.sh 1.0.0
# Outputs: packaging/debian/dist/secureusb_1.0.0_all.deb
```

This package:

- Installs SecureUSB under `/opt/secureusb`
- Drops systemd service, udev rules, polkit policy, D-Bus config, and autostart
- Installs wrappers into `/usr/local/bin`
- Runs dependency installation and setup tasks in `postinst`

> **Note:** The `.deb` expects to be installed with `sudo dpkg -i`. The post-install script invokes `pip3` to install Python dependencies system-wide.

## Signing / Notarization

The scripts do not sign the resulting artifacts. To distribute publicly,
sign/notarize according to each platform's requirements:

- macOS: `productsign`, Apple notarization
- Windows: `signtool.exe`
- Debian: `dpkg-sig` or repository-level signing
