# SecureUSB for Windows 11

This directory contains a native port of SecureUSB for Windows 11 that mirrors
the Linux daemon's functionality: every USB device is immediately disabled via
`pnputil` until the user approves the connection with a TOTP code.

## Requirements

- Windows 11 with administrator privileges (required for `pnputil`)
- Python 3.11+ (64-bit)
- `pip install -r windows/requirements.txt`
- Google Authenticator (or any TOTP app) on your phone

## First-Time Setup

1. **Install Python dependencies**
   ```pwsh
   pip install -r windows/requirements.txt
   ```
2. **Generate the TOTP secret and recovery codes**
   ```pwsh
   python windows/src/setup_cli.py
   ```
   This prints a QR code and saves encrypted credentials to
   `%PROGRAMDATA%\SecureUSB` (or the directory defined by `SECUREUSB_CONFIG_DIR`).
3. **Run the daemon**
   ```pwsh
   python windows/src/app.py
   ```
   Keep the console open, or register the script as a scheduled task to launch at
   logon.

## Running at Startup (Optional)

Create a scheduled task that launches the SecureUSB app at logon:

```pwsh
$python = "C:\Path\To\python.exe"
$script = "C:\Path\To\repo\windows\src\app.py"
Register-ScheduledTask -TaskName "SecureUSB" `
    -Trigger (New-ScheduledTaskTrigger -AtLogOn) `
    -Action (New-ScheduledTaskAction -Execute $python -Argument $script) `
    -RunLevel Highest `
    -Description "SecureUSB authorization guard"
```

## Limitations

- The Windows port relies on `pnputil.exe` and therefore must run elevated.
- Devices may enumerate briefly before they are disabled; use a short polling
  interval to minimise exposure.
- Power-only mode keeps the device disabled (USB still delivers power on most
  hardware, but not all controllers behave identically).

## Troubleshooting

- If `pnputil` reports `"Access is denied"`, make sure you launched the app from
  an elevated console.
- To reset the configuration, delete `%PROGRAMDATA%\SecureUSB` and re-run
  `windows/src/setup_cli.py`.
