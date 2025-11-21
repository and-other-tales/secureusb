#!/bin/bash
#
# Build a Debian package for SecureUSB.
#

set -euo pipefail

VERSION="${1:-1.0.0}"
ARCH="all"
PKG_NAME="secureusb"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
ROOT_DIR="$BUILD_DIR/root"
DEBIAN_DIR="$ROOT_DIR/DEBIAN"
OUTPUT_DIR="$SCRIPT_DIR/dist"

echo "== SecureUSB Debian package builder =="
echo "Version: $VERSION"
echo "Architecture: $ARCH"

rm -rf "$BUILD_DIR"
mkdir -p "$ROOT_DIR" "$DEBIAN_DIR" "$OUTPUT_DIR"

echo "--> Copying application files to /opt/secureusb"
mkdir -p "$ROOT_DIR/opt"
rsync -a "$REPO_ROOT/" "$ROOT_DIR/opt/secureusb/" \
    --exclude ".git" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude "packaging/debian/build" \
    --exclude "windows/msi/build" \
    --exclude "macos/pkg/build"

echo "--> Installing system integration files"
install -d "$ROOT_DIR/etc/systemd/system"
install -m 644 "$REPO_ROOT/data/systemd/secureusb.service" "$ROOT_DIR/etc/systemd/system/secureusb.service"

install -d "$ROOT_DIR/etc/udev/rules.d"
install -m 644 "$REPO_ROOT/data/udev/99-secureusb.rules" "$ROOT_DIR/etc/udev/rules.d/99-secureusb.rules"

install -d "$ROOT_DIR/usr/share/polkit-1/actions"
install -m 644 "$REPO_ROOT/data/polkit/org.secureusb.policy" "$ROOT_DIR/usr/share/polkit-1/actions/org.secureusb.policy"

install -d "$ROOT_DIR/etc/dbus-1/system.d"
install -m 644 "$REPO_ROOT/data/dbus/org.secureusb.Daemon.conf" "$ROOT_DIR/etc/dbus-1/system.d/org.secureusb.Daemon.conf"

install -d "$ROOT_DIR/usr/share/icons/hicolor/scalable/apps"
install -m 644 "$REPO_ROOT/data/icons/hicolor/scalable/apps/"*.svg "$ROOT_DIR/usr/share/icons/hicolor/scalable/apps/"

install -d "$ROOT_DIR/etc/xdg/autostart"
install -m 644 "$REPO_ROOT/data/desktop/secureusb-client.desktop" "$ROOT_DIR/etc/xdg/autostart/secureusb-client.desktop"
install -m 644 "$REPO_ROOT/data/desktop/secureusb-indicator.desktop" "$ROOT_DIR/etc/xdg/autostart/secureusb-indicator.desktop"

echo "--> Creating wrapper scripts"
install -d "$ROOT_DIR/usr/local/bin"

cat > "$ROOT_DIR/usr/local/bin/secureusb-daemon" <<'EOF'
#!/bin/bash
cd /opt/secureusb
exec python3 src/daemon/service.py "$@"
EOF
chmod 755 "$ROOT_DIR/usr/local/bin/secureusb-daemon"

cat > "$ROOT_DIR/usr/local/bin/secureusb-setup" <<'EOF'
#!/bin/bash
cd /opt/secureusb
exec python3 src/gui/setup_wizard.py "$@"
EOF
chmod 755 "$ROOT_DIR/usr/local/bin/secureusb-setup"

cat > "$ROOT_DIR/usr/local/bin/secureusb-client" <<'EOF'
#!/bin/bash
cd /opt/secureusb
exec python3 src/gui/client.py "$@"
EOF
chmod 755 "$ROOT_DIR/usr/local/bin/secureusb-client"

cat > "$ROOT_DIR/usr/local/bin/secureusb-indicator" <<'EOF'
#!/bin/bash
cd /opt/secureusb
exec python3 src/gui/indicator.py "$@"
EOF
chmod 755 "$ROOT_DIR/usr/local/bin/secureusb-indicator"

echo "--> Writing control metadata"
sed "s/@VERSION@/$VERSION/g" "$SCRIPT_DIR/control" > "$DEBIAN_DIR/control"
install -m 755 "$SCRIPT_DIR/postinst" "$DEBIAN_DIR/postinst"
install -m 755 "$SCRIPT_DIR/prerm" "$DEBIAN_DIR/prerm"

echo "--> Building .deb package"
PKG_PATH="$OUTPUT_DIR/${PKG_NAME}_${VERSION}_${ARCH}.deb"
dpkg-deb --build "$ROOT_DIR" "$PKG_PATH"

echo "✓ Debian package created at $PKG_PATH"
