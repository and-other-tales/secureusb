# SecureUSB Quick Start Guide

Get SecureUSB up and running in 5 minutes!

## Step 1: Install

```bash
cd secureusb
sudo ./install.sh
```

Wait for installation to complete. The setup wizard will open automatically.

## Step 2: Configure Google Authenticator

### On Your Phone:
1. Install **Google Authenticator** from your app store
2. Open the app
3. Tap the **+** button
4. Select **"Scan a QR code"**

### On Your Computer:
1. In the setup wizard, you'll see a QR code
2. Scan it with your phone's Google Authenticator app
3. Click **"Next"** in the wizard

## Step 3: Save Recovery Codes

1. The wizard shows 10 recovery codes
2. **Write them down** or **print them**
3. Store them somewhere safe (not on your computer!)
4. Check the box "I have saved these recovery codes"
5. Click **"Next"**

## Step 4: Test Your Setup

1. Open Google Authenticator on your phone
2. Find the **SecureUSB** entry
3. You'll see a 6-digit code (changes every 30 seconds)
4. Enter this code in the wizard
5. Click **"Verify Code"**

✓ If correct, you'll see "Setup Complete!"

## Step 5: Try It Out!

1. Plug in a USB device (flash drive, mouse, keyboard, etc.)
2. You'll see an authorization dialog
3. Open Google Authenticator on your phone
4. Enter the 6-digit code
5. Click **"Connect"**

Your device is now authorized and will work normally!

## Daily Usage

### To Allow a Device:
1. Plug in device
2. Dialog appears
3. Enter TOTP code from phone
4. Click "Connect"

### To Block a Device:
1. Plug in device
2. Dialog appears
3. Click "Deny"

### For Charging Only (Phone/Tablet):
1. Plug in device
2. Dialog appears
3. Enter TOTP code
4. Click "Power Only"

## Troubleshooting

### Dialog doesn't appear?
```bash
# Start the client manually
secureusb-client
```

### Daemon not running?
```bash
# Check status
sudo systemctl status secureusb

# Start it
sudo systemctl start secureusb
```

### Lost your phone?
Use a recovery code instead of the TOTP code in the authorization dialog.

### Need to reconfigure?
```bash
# Run setup wizard again
secureusb-setup
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `secureusb-setup` | Run setup wizard |
| `secureusb-client` | Start GUI client |
| `sudo systemctl status secureusb` | Check daemon status |
| `sudo systemctl restart secureusb` | Restart daemon |
| `sudo systemctl stop secureusb` | Stop daemon (allows all USB) |
| `sudo journalctl -u secureusb -f` | View daemon logs |

## Tips

- **Whitelist frequent devices**: Check "Remember this device" in the dialog
- **Keep recovery codes safe**: You'll need them if you lose your phone
- **One code per device**: You can't reuse the same TOTP code twice
- **30-second window**: TOTP codes expire every 30 seconds

## Need Help?

- Full documentation: See [README.md](README.md)
- Report issues: https://github.com/yourusername/secureusb/issues

---

**Security Reminder**:
- Never share your TOTP secret or QR code
- Keep recovery codes offline and secure
- Don't authorize unknown devices
