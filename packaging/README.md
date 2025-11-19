# SecureUSB Packaging

This directory contains helper scripts for producing the native Debian/Ubuntu
installer:

- **Debian `.deb`** – builds a dpkg archive that installs SecureUSB into
  `/opt/secureusb`, registers the systemd unit/udev rules/polkit policy,
  and prepares the GNOME indicator autostart entry.

All packaging scripts assume they are executed from the repository root.

## Debian Packaging Flow

```mermaid
flowchart LR
    Repo[SecureUSB Repo] -->|packaging/debian/build_deb.sh| DebPkg[secureusb_<ver>_all.deb]
    DebPkg -->|install| DebTarget[/Debian/Ubuntu host/]
```

## Debian/Ubuntu (`packaging/debian/build_deb.sh`)

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

## Signing

The script does not sign the resulting artifact. To distribute publicly,
consider signing the package with `dpkg-sig` or publishing via a signed APT
repository.
