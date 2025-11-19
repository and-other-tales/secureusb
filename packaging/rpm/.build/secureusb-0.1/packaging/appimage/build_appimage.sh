#!/bin/bash
#
# Build a SecureUSB AppImage.
#

set -euo pipefail

VERSION="${1:-1.0.0}"
APP_NAME="SecureUSB"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORK_DIR="$SCRIPT_DIR/build"
APPDIR="$WORK_DIR/${APP_NAME}.AppDir"
OUTPUT_DIR="$SCRIPT_DIR/dist"

mkdir -p "$OUTPUT_DIR"
rm -rf "$WORK_DIR"
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"

echo "== SecureUSB AppImage builder =="
echo "Version : $VERSION"

echo "--> Bundling application files"
rsync -a "$REPO_ROOT/" "$APPDIR/usr/lib/secureusb/" \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.venv' \
    --exclude '.coverage' \
    --exclude 'packaging/rpm/rpmbuild' \
    --exclude 'packaging/appimage/build'

echo "--> Creating launcher scripts"
cat > "$APPDIR/usr/bin/secureusb-client" <<'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
ROOT="$(cd "$HERE/../lib/secureusb" && pwd)"
export PYTHONPATH="$ROOT:$PYTHONPATH"
cd "$ROOT"
exec python3 src/gui/client.py "$@"
EOF
chmod 0755 "$APPDIR/usr/bin/secureusb-client"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/secureusb-client" "$@"
EOF
chmod 0755 "$APPDIR/AppRun"

echo "--> Writing desktop entry"
cat > "$APPDIR/${APP_NAME}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=${APP_NAME}
Comment=Secure USB Device Authorization Client
Exec=secureusb-client
Icon=secureusb
Categories=System;Security;
Terminal=false
EOF

echo "--> Creating placeholder icon"
ICON_PATH="$APPDIR/usr/share/icons/hicolor/256x256/apps/secureusb.png"
python3 - "$ICON_PATH" <<'PY'
import base64
import pathlib
import sys
icon_path = pathlib.Path(sys.argv[1])
icon_path.parent.mkdir(parents=True, exist_ok=True)
icon_path.write_bytes(base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAIAAABmxkRkAAAACXBIWXMAAAsTAAALEwEAmpwY"
    "AAAAG0lEQVR4nO3BMQEAAADCoPdPbQ43oAAAAAAAAAAA8GsAARg7Gz4AAAAASUVORK5CYII="
))
PY

APPIMAGETOOL_BIN="${APPIMAGETOOL:-$(command -v appimagetool || true)}"
if [[ -z "$APPIMAGETOOL_BIN" ]]; then
    echo "✗ appimagetool not found in PATH. Set APPIMAGETOOL or install appimagetool to finish the build." >&2
    exit 2
fi

echo "--> Running appimagetool"
"$APPIMAGETOOL_BIN" "$APPDIR" "$OUTPUT_DIR/${APP_NAME}-${VERSION}.AppImage"
echo "✓ AppImage created at $OUTPUT_DIR/${APP_NAME}-${VERSION}.AppImage"
