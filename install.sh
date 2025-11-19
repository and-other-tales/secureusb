#!/bin/bash
#
# SecureUSB Installation Script
# Installs and configures SecureUSB on Ubuntu 25.04
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
print_header() {
    echo -e "${BLUE}====================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}====================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "This script must be run as root"
    echo "Please run: sudo ./install.sh"
    exit 1
fi

# Get the actual user (not root)
if [ -n "$SUDO_USER" ]; then
    ACTUAL_USER="$SUDO_USER"
    ACTUAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    ACTUAL_USER="$USER"
    ACTUAL_HOME="$HOME"
fi

print_header "SecureUSB Installation"
echo "Installing SecureUSB for user: $ACTUAL_USER"
echo "User home directory: $ACTUAL_HOME"
echo ""

# Confirm installation
read -p "Do you want to continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "Installation cancelled"
    exit 0
fi

print_header "Step 1: Checking System Requirements"

# Check Ubuntu version
if [ -f /etc/os-release ]; then
    . /etc/os-release
    print_info "OS: $NAME $VERSION"
else
    print_warning "Could not determine OS version"
fi

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
print_info "Python version: $PYTHON_VERSION"

if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed"
    exit 1
fi

print_success "System requirements check passed"
echo ""

print_header "Step 2: Installing System Dependencies"

# Update package list
print_info "Updating package list..."
apt-get update -qq

# Install required packages
# Determine correct polkit package (policykit-1 was removed in newer releases)
POLKIT_PACKAGE="policykit-1"
if apt-cache policy policykit-1 | grep -q "Candidate: (none)"; then
    POLKIT_PACKAGE="polkitd"
    print_warning "policykit-1 not available; falling back to polkitd"
fi

PACKAGES=(
    "python3-pip"
    "python3-gi"
    "python3-dbus"
    "gir1.2-gtk-4.0"
    "gir1.2-gtk-3.0"
    "gir1.2-ayatanaappindicator3-0.1"
    "gir1.2-adw-1"
    "libgirepository1.0-dev"
    "udev"
    "$POLKIT_PACKAGE"
)

for package in "${PACKAGES[@]}"; do
    if dpkg -l | grep -q "^ii  $package "; then
        print_success "$package already installed"
    else
        print_info "Installing $package..."
        apt-get install -y -qq "$package" || {
            print_error "Failed to install $package"
            exit 1
        }
        print_success "$package installed"
    fi
done

echo ""

print_header "Step 3: Installing Python Dependencies"

# Install Python packages
print_info "Installing Python packages..."

pip3 install --quiet --break-system-packages pyudev pyotp qrcode[pil] cryptography pillow || {
    print_error "Failed to install Python dependencies"
    exit 1
}

print_success "Python dependencies installed"
echo ""

print_header "Step 4: Installing SecureUSB Files"

# Create installation directory
INSTALL_DIR="/opt/secureusb"
print_info "Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Copy source files
print_info "Copying source files..."
cp -r src "$INSTALL_DIR/"
cp requirements.txt "$INSTALL_DIR/"

# Create __init__.py in src if missing
touch "$INSTALL_DIR/src/__init__.py"

print_success "Source files installed"

# Install udev rules
print_info "Installing udev rules..."
cp data/udev/99-secureusb.rules /etc/udev/rules.d/
udevadm control --reload-rules
print_success "Udev rules installed"

# Install systemd service
print_info "Installing systemd service..."
cp data/systemd/secureusb.service /etc/systemd/system/
systemctl daemon-reload
print_success "Systemd service installed"

# Install polkit policy
print_info "Installing polkit policy..."
mkdir -p /usr/share/polkit-1/actions
cp data/polkit/org.secureusb.policy /usr/share/polkit-1/actions/
print_success "Polkit policy installed"

# Install D-Bus configuration
print_info "Installing D-Bus configuration..."
mkdir -p /etc/dbus-1/system.d
cp data/dbus/org.secureusb.Daemon.conf /etc/dbus-1/system.d/
print_success "D-Bus configuration installed"

# Install application icons
print_info "Installing application icons..."
mkdir -p /usr/share/icons/hicolor/scalable/apps
cp data/icons/hicolor/scalable/apps/*.svg /usr/share/icons/hicolor/scalable/apps/
# Update icon cache if gtk-update-icon-cache is available
if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
fi
print_success "Application icons installed"

# Install desktop autostart file (for user)
print_info "Installing autostart files..."
AUTOSTART_DIR="$ACTUAL_HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
cp data/desktop/secureusb-client.desktop "$AUTOSTART_DIR/"
cp data/desktop/secureusb-indicator.desktop "$AUTOSTART_DIR/"
chown -R "$ACTUAL_USER:$ACTUAL_USER" "$AUTOSTART_DIR"
print_success "Autostart files installed"

# Create wrapper scripts
print_info "Creating wrapper scripts..."

# Daemon script
cat > /usr/local/bin/secureusb-daemon << 'EOF'
#!/bin/bash
cd /opt/secureusb
exec python3 src/daemon/service.py "$@"
EOF
chmod +x /usr/local/bin/secureusb-daemon

# Setup wizard script
cat > /usr/local/bin/secureusb-setup << 'EOF'
#!/bin/bash
cd /opt/secureusb
exec python3 src/gui/setup_wizard.py "$@"
EOF
chmod +x /usr/local/bin/secureusb-setup

# Client script
cat > /usr/local/bin/secureusb-client << 'EOF'
#!/bin/bash
cd /opt/secureusb
exec python3 src/gui/client.py "$@"
EOF
chmod +x /usr/local/bin/secureusb-client

# Indicator script
cat > /usr/local/bin/secureusb-indicator << 'EOF'
#!/bin/bash
cd /opt/secureusb
exec python3 src/gui/indicator.py "$@"
EOF
chmod +x /usr/local/bin/secureusb-indicator

print_success "Wrapper scripts created"
echo ""

print_header "Step 4.5: Preparing Shared Configuration"

CONFIG_DIR="/var/lib/secureusb"
LEGACY_CONFIG_DIR="$ACTUAL_HOME/.config/secureusb"

print_info "Ensuring shared config directory exists at $CONFIG_DIR"
mkdir -p "$CONFIG_DIR"

# Migrate existing per-user config if present and shared dir is empty
if [ -d "$LEGACY_CONFIG_DIR" ] && [ -z "$(ls -A "$CONFIG_DIR" 2>/dev/null)" ]; then
    print_info "Migrating existing configuration from $LEGACY_CONFIG_DIR"
    cp -a "$LEGACY_CONFIG_DIR/." "$CONFIG_DIR/"
fi

chown -R "$ACTUAL_USER:$ACTUAL_USER" "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

mkdir -p /etc/secureusb
echo "$CONFIG_DIR" > /etc/secureusb/config_dir
print_success "Shared configuration directory ready"
echo ""

print_header "Step 5: Configuring SecureUSB"

# Check if already configured
if [ -f "$CONFIG_DIR/auth.enc" ]; then
    print_warning "SecureUSB is already configured"
    print_info "Skipping setup wizard"
else
    print_info "Running setup wizard for user $ACTUAL_USER..."
    echo ""

    # Run setup wizard as actual user
    sudo -u "$ACTUAL_USER" DISPLAY=:0 /usr/local/bin/secureusb-setup &

    print_info "Setup wizard launched"
    print_info "Please complete the setup wizard to configure TOTP authentication"
fi

echo ""

print_header "Step 6: Enabling Services"

# Enable systemd service
print_info "Enabling SecureUSB daemon..."
systemctl enable secureusb.service
print_success "Daemon enabled (will start on boot)"

# Start daemon
print_info "Starting SecureUSB daemon..."
systemctl start secureusb.service || {
    print_warning "Could not start daemon (may need configuration first)"
}

# Check daemon status
if systemctl is-active --quiet secureusb.service; then
    print_success "Daemon is running"
else
    print_warning "Daemon is not running (run setup wizard first)"
fi

echo ""

print_header "Installation Complete!"
echo ""
print_success "SecureUSB has been installed successfully"
echo ""
echo "Next steps:"
echo "  1. Complete the setup wizard to configure TOTP authentication"
echo "     (should open automatically, or run: secureusb-setup)"
echo ""
echo "  2. Scan the QR code with Google Authenticator on your phone"
echo ""
echo "  3. Save the recovery codes in a safe place"
echo ""
echo "  4. Reboot your system for full protection"
echo "     (or run: sudo systemctl restart secureusb)"
echo ""
echo "Commands:"
echo "  secureusb-setup  - Run setup wizard"
echo "  secureusb-client - Start GUI client"
echo "  sudo systemctl status secureusb - Check daemon status"
echo "  sudo systemctl restart secureusb - Restart daemon"
echo ""

# Check if GNOME Shell is running and extension is not installed
if pgrep -x "gnome-shell" > /dev/null 2>&1; then
    if ! gnome-extensions list --enabled 2>/dev/null | grep -qi appindicator; then
        print_warning "GNOME AppIndicator Extension Not Detected!"
        echo ""
        echo "Modern GNOME requires the AppIndicator extension to show the tray icon."
        echo ""
        echo "Install it with one of these methods:"
        echo "  Method 1 (Recommended):"
        echo "    sudo apt install gnome-shell-extension-appindicator"
        echo "    gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com"
        echo ""
        echo "  Method 2 (Manual):"
        echo "    Visit: https://extensions.gnome.org/extension/615/appindicator-support/"
        echo ""
        echo "Then restart GNOME Shell (Alt+F2, type 'r', press Enter)"
        echo ""
    fi
fi

print_info "When you plug in a USB device, you'll see an authorization dialog"
print_info "Enter your TOTP code to allow the device to connect"
echo ""

# Wait for setup wizard if running
if pgrep -f "setup_wizard.py" > /dev/null; then
    echo "Waiting for setup wizard to complete..."
    echo "(You can close this terminal and complete the wizard)"
fi
