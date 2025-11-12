# SecureUSB for macOS (Monterey+)

This directory hosts a native macOS implementation of SecureUSB that mirrors
the Linux daemon: every USB device is suspended as soon as it is detected and
is only re-enabled after successful TOTP authentication.

## Requirements

- macOS 12 (Monterey) or newer
- Python 3.11+ from Xcode command-line tools or Homebrew
- `pip install -r macos/requirements.txt`
- Google Authenticator (or any compatible TOTP app)
- The SecureUSB agent must run with administrator privileges to toggle USB ports

## Installation

1. Install Python dependencies:
   ```bash
   python3 -m pip install -r macos/requirements.txt
   ```
2. Create the encrypted TOTP secret and recovery codes:
   ```bash
   python3 macos/src/setup_cli.py
   ```
   The credentials are stored in `/Library/Application Support/SecureUSB` (or the
   path defined by `SECUREUSB_CONFIG_DIR`).
3. Launch the daemon:
   ```bash
   sudo python3 macos/src/app.py
   ```
   The app keeps a tiny PySide6 window hidden in the background and displays the
   authorization dialog whenever a USB device connects.

To run automatically on login, install the launch agent via `macos/install.sh`
or create your own LaunchAgent pointing to `macos/src/app.py`.

## Limitations

- IOKit does not expose an officially supported per-device "power only" mode, so
  the implementation toggles the `USB PortDisable` property and falls back to
  `diskutil unmountDisk` for mass-storage devices. Some controllers may require
  unplug/replug after approval.
- Because the agent interacts with IOKit, it must run with elevated privileges
  (either via `sudo` or a privileged launch daemon).

## Troubleshooting

- If the dialog never appears, ensure `system_profiler SPUSBDataType -json`
  works without prompts and that Python has Full Disk Access (for reading the
  config directory).
- To reconfigure TOTP, delete `/Library/Application Support/SecureUSB` and rerun
  `macos/src/setup_cli.py`.
