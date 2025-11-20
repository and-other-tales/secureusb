#!/bin/bash
#
# Build a macOS .pkg installer for SecureUSB
#
# Usage: ./build_pkg.sh [VERSION]
# Example: ./build_pkg.sh 1.0.0
#

set -euo pipefail

VERSION="${1:-1.0.0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
PAYLOAD_DIR="$BUILD_DIR/payload"
SCRIPTS_DIR="$SCRIPT_DIR/scripts"
RESOURCES_DIR="$SCRIPT_DIR/Resources"
OUTPUT_DIR="$SCRIPT_DIR/dist"
PKG_NAME="SecureUSB"
PKG_IDENTIFIER="org.secureusb"
COMPONENT_PKG="$BUILD_DIR/secureusb-component.pkg"
FINAL_PKG="$OUTPUT_DIR/${PKG_NAME}-${VERSION}.pkg"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo_step() {
    echo -e "${CYAN}==>${NC} $1"
}

echo_success() {
    echo -e "${GREEN}✓${NC} $1"
}

echo_error() {
    echo -e "${RED}✗${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check for required tools
check_dependencies() {
    echo_step "Checking dependencies..."

    local missing_deps=()

    if ! command -v pkgbuild >/dev/null 2>&1; then
        missing_deps+=("pkgbuild")
    fi

    if ! command -v productbuild >/dev/null 2>&1; then
        missing_deps+=("productbuild")
    fi

    if ! command -v python3 >/dev/null 2>&1; then
        missing_deps+=("python3")
    fi

    if [ ${#missing_deps[@]} -ne 0 ]; then
        echo_error "Missing required dependencies: ${missing_deps[*]}"
        echo ""
        echo "Please install Xcode Command Line Tools:"
        echo "  xcode-select --install"
        exit 1
    fi

    echo_success "All dependencies found"
}

# Print banner
echo ""
echo "============================================"
echo " SecureUSB macOS PKG Builder"
echo "============================================"
echo "Version: $VERSION"
echo "Output: $FINAL_PKG"
echo ""

check_dependencies

# Clean and create build directories
echo_step "Preparing build directories..."
rm -rf "$BUILD_DIR"
mkdir -p "$PAYLOAD_DIR"
mkdir -p "$OUTPUT_DIR"
echo_success "Build directories ready"

# Copy application files to payload
echo_step "Copying application files..."

# Create the installation directory structure
mkdir -p "$PAYLOAD_DIR/opt/secureusb"

# Copy main source directories
rsync -a "$REPO_ROOT/src/" "$PAYLOAD_DIR/opt/secureusb/src/" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude "*.pyo" \
    --exclude ".DS_Store"

rsync -a "$REPO_ROOT/data/" "$PAYLOAD_DIR/opt/secureusb/data/" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude ".DS_Store"

rsync -a "$REPO_ROOT/ports/" "$PAYLOAD_DIR/opt/secureusb/ports/" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude ".DS_Store"

# Copy macOS-specific files
mkdir -p "$PAYLOAD_DIR/opt/secureusb/macos"
cp "$REPO_ROOT/macos/requirements.txt" "$PAYLOAD_DIR/opt/secureusb/macos/"
cp "$REPO_ROOT/macos/org.secureusb.daemon.plist" "$PAYLOAD_DIR/opt/secureusb/macos/"

# Copy documentation
cp "$REPO_ROOT/README.md" "$PAYLOAD_DIR/opt/secureusb/"
cp "$REPO_ROOT/LICENSE" "$PAYLOAD_DIR/opt/secureusb/"
cp "$REPO_ROOT/EULA.md" "$PAYLOAD_DIR/opt/secureusb/"

# Copy requirements.txt
cp "$REPO_ROOT/requirements.txt" "$PAYLOAD_DIR/opt/secureusb/"

echo_success "Application files copied"

# Set correct permissions
echo_step "Setting file permissions..."
chmod -R 755 "$PAYLOAD_DIR/opt/secureusb"
find "$PAYLOAD_DIR/opt/secureusb" -type f -name "*.py" -exec chmod 644 {} \;
echo_success "Permissions set"

# Make scripts executable
echo_step "Preparing installation scripts..."
chmod +x "$SCRIPTS_DIR/preinstall"
chmod +x "$SCRIPTS_DIR/postinstall"
echo_success "Installation scripts ready"

# Prepare resources
echo_step "Preparing installer resources..."

# Copy LICENSE for the installer
cp "$REPO_ROOT/LICENSE" "$RESOURCES_DIR/LICENSE.txt"

# Check if welcome and conclusion HTML files exist
if [ ! -f "$RESOURCES_DIR/welcome.html" ]; then
    echo_warning "welcome.html not found, creating default..."
    cat > "$RESOURCES_DIR/welcome.html" <<EOF
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Welcome</title></head>
<body><h1>Welcome to SecureUSB</h1><p>This will install SecureUSB on your Mac.</p></body>
</html>
EOF
fi

if [ ! -f "$RESOURCES_DIR/conclusion.html" ]; then
    echo_warning "conclusion.html not found, creating default..."
    cat > "$RESOURCES_DIR/conclusion.html" <<EOF
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Installation Complete</title></head>
<body><h1>Installation Complete</h1><p>Run 'sudo secureusb-macos setup' to configure SecureUSB.</p></body>
</html>
EOF
fi

echo_success "Resources prepared"

# Build component package
echo_step "Building component package..."
pkgbuild \
    --root "$PAYLOAD_DIR" \
    --scripts "$SCRIPTS_DIR" \
    --identifier "$PKG_IDENTIFIER" \
    --version "$VERSION" \
    --install-location "/" \
    "$COMPONENT_PKG"

if [ $? -ne 0 ]; then
    echo_error "Failed to build component package"
    exit 1
fi

echo_success "Component package created"

# Create distribution file from template
echo_step "Creating distribution definition..."
DISTRIBUTION_FILE="$BUILD_DIR/distribution.xml"
sed "s/VERSION_PLACEHOLDER/$VERSION/g" "$SCRIPT_DIR/distribution-template.xml" > "$DISTRIBUTION_FILE"

# Remove background reference if file doesn't exist
if [ ! -f "$RESOURCES_DIR/background.png" ]; then
    sed -i.bak '/<background/d' "$DISTRIBUTION_FILE"
    rm -f "$DISTRIBUTION_FILE.bak"
fi

# Remove license reference if file doesn't exist (we have LICENSE.txt from above)
if [ ! -f "$RESOURCES_DIR/LICENSE.txt" ]; then
    sed -i.bak '/<license/d' "$DISTRIBUTION_FILE"
    rm -f "$DISTRIBUTION_FILE.bak"
fi

echo_success "Distribution file created"

# Build product package
echo_step "Building final installer package..."
productbuild \
    --distribution "$DISTRIBUTION_FILE" \
    --resources "$RESOURCES_DIR" \
    --package-path "$BUILD_DIR" \
    --version "$VERSION" \
    "$FINAL_PKG"

if [ $? -ne 0 ]; then
    echo_error "Failed to build product package"
    exit 1
fi

echo_success "Final package created"

# Get package size
PKG_SIZE=$(du -h "$FINAL_PKG" | cut -f1)

# Display results
echo ""
echo "============================================"
echo -e "${GREEN} Build Complete!${NC}"
echo "============================================"
echo ""
echo "Package: $FINAL_PKG"
echo "Size: $PKG_SIZE"
echo "Version: $VERSION"
echo ""
echo "To install:"
echo "  sudo installer -pkg \"$FINAL_PKG\" -target /"
echo ""
echo "Or double-click the .pkg file to install via GUI"
echo ""
echo "After installation, run:"
echo "  sudo secureusb-macos setup"
echo ""

# Optional: Sign the package
if command -v productsign >/dev/null 2>&1; then
    echo_warning "Package is unsigned. To sign it for distribution:"
    echo ""
    echo "  productsign --sign \"Developer ID Installer: Your Name\" \\"
    echo "    \"$FINAL_PKG\" \\"
    echo "    \"${FINAL_PKG%.pkg}-signed.pkg\""
    echo ""
fi

echo_success "Build complete!"
exit 0
