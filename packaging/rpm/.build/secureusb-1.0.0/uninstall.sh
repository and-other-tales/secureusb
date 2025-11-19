#!/bin/bash
#
# SecureUSB Uninstallation Script
# Removes SecureUSB from the system
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Check root
if [ "$EUID" -ne 0 ]; then
    print_error "This script must be run as root"
    echo "Please run: sudo ./uninstall.sh"
    exit 1
fi

# Get actual user
if [ -n "$SUDO_USER" ]; then
    ACTUAL_USER="$SUDO_USER"
    ACTUAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    ACTUAL_USER="$USER"
    ACTUAL_HOME="$HOME"
fi

print_header "SecureUSB Uninstallation"
echo ""

CONFIG_DIR="/var/lib/secureusb"
POINTER_FILE="/etc/secureusb/config_dir"
LEGACY_CONFIG_DIR="$ACTUAL_HOME/.config/secureusb"
if [ -f "$POINTER_FILE" ]; then
    CONFIG_DIR=$(cat "$POINTER_FILE")
fi

print_warning "This will remove SecureUSB from your system"
print_warning "USB devices will be allowed automatically after uninstallation"
echo ""
read -p "Do you want to continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "Uninstallation cancelled"
    exit 0
fi

echo ""
print_header "Removing SecureUSB"

# Stop and disable daemon
print_info "Stopping SecureUSB daemon..."
systemctl stop secureusb.service 2>/dev/null || true
systemctl disable secureusb.service 2>/dev/null || true
print_success "Daemon stopped and disabled"

# Remove systemd service
print_info "Removing systemd service..."
rm -f /etc/systemd/system/secureusb.service
systemctl daemon-reload
print_success "Systemd service removed"

# Remove udev rules
print_info "Removing udev rules..."
rm -f /etc/udev/rules.d/99-secureusb.rules
udevadm control --reload-rules
print_success "Udev rules removed"

# Remove polkit policy
print_info "Removing polkit policy..."
rm -f /usr/share/polkit-1/actions/org.secureusb.policy
print_success "Polkit policy removed"

# Remove D-Bus configuration
print_info "Removing D-Bus configuration..."
rm -f /etc/dbus-1/system.d/org.secureusb.Daemon.conf
print_success "D-Bus configuration removed"

# Remove autostart file
print_info "Removing autostart file..."
rm -f "$ACTUAL_HOME/.config/autostart/secureusb-client.desktop"
rm -f "$ACTUAL_HOME/.config/autostart/secureusb-indicator.desktop"
print_success "Autostart file removed"

# Remove wrapper scripts
print_info "Removing wrapper scripts..."
rm -f /usr/local/bin/secureusb-daemon
rm -f /usr/local/bin/secureusb-setup
rm -f /usr/local/bin/secureusb-client
rm -f /usr/local/bin/secureusb-indicator
print_success "Wrapper scripts removed"

# Remove installation directory
print_info "Removing installation directory..."
rm -rf /opt/secureusb
print_success "Installation directory removed"

# Ask about user configuration
echo ""
print_warning "User configuration files contain TOTP secrets and logs"
read -p "Do you want to remove SecureUSB configuration data? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Removing user configuration..."
    rm -rf "$CONFIG_DIR"
    if [ -d "$LEGACY_CONFIG_DIR" ] && [ "$LEGACY_CONFIG_DIR" != "$CONFIG_DIR" ]; then
        rm -rf "$LEGACY_CONFIG_DIR"
        print_info "Legacy per-user configuration removed from $LEGACY_CONFIG_DIR"
    fi
    print_success "Configuration removed"
else
    print_info "Configuration preserved at: $CONFIG_DIR"
fi

rm -f "$POINTER_FILE"
rmdir /etc/secureusb 2>/dev/null || true

# Re-enable USB devices
print_info "Re-enabling USB authorization..."
for controller in /sys/bus/usb/devices/usb*/authorized_default; do
    if [ -f "$controller" ]; then
        echo 1 > "$controller" 2>/dev/null || true
    fi
done
print_success "USB authorization re-enabled"

echo ""
print_header "Uninstallation Complete"
echo ""
print_success "SecureUSB has been removed from your system"
echo ""
print_info "USB devices will now be automatically authorized"
print_info "A reboot is recommended to ensure all changes take effect"
echo ""
