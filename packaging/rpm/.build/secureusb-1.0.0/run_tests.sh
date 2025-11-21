#!/bin/bash
#
# Test Runner Script for SecureUSB
# Runs all unit tests and displays results
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

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    print_info "Virtual environment not found. Creating..."
    python3 -m venv --system-site-packages .venv
    .venv/bin/pip install --quiet pyudev pyotp qrcode[pil] cryptography pillow
    print_success "Virtual environment created"
fi

print_header "SecureUSB Test Suite"
echo ""

# Run tests based on argument
case "${1:-all}" in
    totp)
        print_info "Running TOTP authentication tests..."
        .venv/bin/python -m unittest tests.test_totp -v
        ;;
    storage)
        print_info "Running secure storage tests..."
        .venv/bin/python -m unittest tests.test_storage -v
        ;;
    logger)
        print_info "Running logger tests..."
        .venv/bin/python -m unittest tests.test_logger -v
        ;;
    config)
        print_info "Running configuration tests..."
        .venv/bin/python -m unittest tests.test_config -v
        ;;
    whitelist)
        print_info "Running whitelist tests..."
        .venv/bin/python -m unittest tests.test_whitelist -v
        ;;
    all)
        print_info "Running all unit tests..."
        echo ""
        .venv/bin/python -m unittest discover tests -v
        ;;
    coverage)
        print_info "Running tests with coverage..."
        if ! .venv/bin/pip show coverage > /dev/null 2>&1; then
            print_info "Installing coverage..."
            .venv/bin/pip install --quiet coverage
        fi
        .venv/bin/python -m coverage run -m unittest discover tests
        .venv/bin/python -m coverage report
        .venv/bin/python -m coverage html
        print_success "Coverage report generated in htmlcov/index.html"
        ;;
    *)
        echo "Usage: $0 [totp|storage|logger|config|whitelist|all|coverage]"
        echo ""
        echo "Options:"
        echo "  totp      - Run TOTP authentication tests"
        echo "  storage   - Run secure storage tests"
        echo "  logger    - Run logger tests"
        echo "  config    - Run configuration tests"
        echo "  whitelist - Run whitelist tests"
        echo "  all       - Run all unit tests (default)"
        echo "  coverage  - Run tests with coverage report"
        exit 1
        ;;
esac

echo ""
if [ $? -eq 0 ]; then
    print_success "All tests passed!"
else
    print_error "Some tests failed"
    exit 1
fi
