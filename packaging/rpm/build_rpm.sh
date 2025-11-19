#!/bin/bash
#
# Build a SecureUSB RPM package using rpmbuild.
#

set -euo pipefail

VERSION="${1:-1.0.0}"
RELEASE="${2:-1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RPM_TOP="$SCRIPT_DIR/rpmbuild"
TMP_DIR="$RPM_TOP/tmp"
SOURCES_DIR="$RPM_TOP/SOURCES"
SPECS_DIR="$RPM_TOP/SPECS"
BUILD_DIR="$SCRIPT_DIR/.build"

echo "== SecureUSB RPM builder =="
echo "Version : $VERSION"
echo "Release : $RELEASE"

rm -rf "$RPM_TOP" "$BUILD_DIR"
mkdir -p "$SOURCES_DIR" "$SPECS_DIR" "$BUILD_DIR" "$TMP_DIR"

echo "--> Staging sources"
STAGING="$BUILD_DIR/secureusb-$VERSION"
rsync -a "$REPO_ROOT/" "$STAGING/" \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'packaging/rpm/rpmbuild' \
    --exclude '.venv' \
    --exclude '.coverage'

TARBALL="$SOURCES_DIR/secureusb-$VERSION.tar.gz"
tar -C "$BUILD_DIR" -czf "$TARBALL" "secureusb-$VERSION"
echo "    Created source tarball $TARBALL"

SPEC_FILE="$SPECS_DIR/secureusb.spec"
sed -e "s/@VERSION@/$VERSION/g" \
    -e "s/@RELEASE@/$RELEASE/g" \
    "$SCRIPT_DIR/secureusb.spec.template" > "$SPEC_FILE"

echo "--> Running rpmbuild"
rpmbuild --define "_topdir $RPM_TOP" --define "_tmppath $TMP_DIR" -bb "$SPEC_FILE"

RPM_PATH="$(find "$RPM_TOP/RPMS" -name 'secureusb-*.rpm' -print -quit)"
if [[ -f "$RPM_PATH" ]]; then
    echo "✓ RPM created at $RPM_PATH"
else
    echo "✗ rpmbuild completed but no RPM found" >&2
    exit 1
fi
