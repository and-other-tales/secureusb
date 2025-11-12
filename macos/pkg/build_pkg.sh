#!/bin/bash
#
# Build a macOS SecureUSB installer (.pkg) using pkgbuild.
#

set -euo pipefail

VERSION="${1:-1.0.0}"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
PKG_ROOT="$BUILD_DIR/root"
OUTPUT_DIR="$SCRIPT_DIR/dist"

echo "== SecureUSB macOS pkg builder =="
echo "Version: $VERSION"
echo "Python:  $PYTHON_BIN"
echo "Repo:    $REPO_ROOT"

rm -rf "$BUILD_DIR"
mkdir -p "$PKG_ROOT/opt/secureusb" "$PKG_ROOT/usr/local/bin" "$PKG_ROOT/Library/LaunchDaemons" "$OUTPUT_DIR"

echo "--> Copying SecureUSB sources to pkg root"
rsync -a "$REPO_ROOT/" "$PKG_ROOT/opt/secureusb/" \
    --exclude ".git" \
    --exclude "__pycache__" \
    --exclude ".mypy_cache" \
    --exclude "macos/pkg/build" \
    --exclude "windows/msi/build" \
    --exclude "*.pyc"

echo "--> Installing LaunchDaemon plist"
install -m 644 "$SCRIPT_DIR/launchd/org.secureusb.agent.plist" "$PKG_ROOT/Library/LaunchDaemons/org.secureusb.agent.plist"

echo "--> Creating wrapper scripts"
cat > "$PKG_ROOT/usr/local/bin/secureusb-setup" <<'EOF'
#!/bin/bash
cd /opt/secureusb
/usr/bin/env python3 macos/src/setup_cli.py "$@"
EOF
chmod 755 "$PKG_ROOT/usr/local/bin/secureusb-setup"

cat > "$PKG_ROOT/usr/local/bin/secureusb-macos" <<'EOF'
#!/bin/bash
cd /opt/secureusb
/usr/bin/env sudo /usr/bin/python3 macos/src/app.py "$@"
EOF
chmod 755 "$PKG_ROOT/usr/local/bin/secureusb-macos"

echo "--> Preparing pkgbuild scripts"
SCRIPTS_DIR="$SCRIPT_DIR/scripts"
chmod 755 "$SCRIPTS_DIR/postinstall" "$SCRIPTS_DIR/preinstall"

PKG_PATH="$OUTPUT_DIR/SecureUSB-$VERSION.pkg"

pkgbuild \
    --identifier org.secureusb.agent \
    --version "$VERSION" \
    --root "$PKG_ROOT" \
    --scripts "$SCRIPTS_DIR" \
    "$PKG_PATH"

echo "✓ macOS package created at $PKG_PATH"
