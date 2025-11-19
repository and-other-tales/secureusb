# SecureUSB Test Suite

Comprehensive unit and integration tests for all SecureUSB modules.

## Test Coverage

### Authentication Module Tests (`test_totp.py`)

**TOTPAuthenticator Tests:**
- ✅ Initialization with and without secret
- ✅ Secret key generation and retrieval
- ✅ Provisioning URI generation for QR codes
- ✅ TOTP code generation
- ✅ TOTP code verification (valid/invalid)
- ✅ Code format validation
- ✅ Code reuse prevention
- ✅ Time remaining calculation
- ✅ Handling codes with spaces

**RecoveryCodeManager Tests:**
- ✅ Recovery code generation (default and custom count)
- ✅ Code format validation (XXXX-XXXX-XXXX)
- ✅ Code uniqueness
- ✅ Code hashing (SHA-256)
- ✅ Hash consistency
- ✅ Code verification (valid/invalid)
- ✅ Case-insensitive verification
- ✅ Code formatting

**Total: 26 tests**

### Secure Storage Tests (`test_storage.py`)

- ✅ Storage initialization
- ✅ Configuration status checking
- ✅ Saving authentication data
- ✅ Loading authentication data
- ✅ Save/load data integrity
- ✅ Recovery code removal
- ✅ Recovery code counting
- ✅ Authentication reset
- ✅ Configuration export/import
- ✅ File permissions (700 for directory, 600 for files)
- ✅ Encryption (AES-256 with Fernet)

**Total: 15 tests**

### Logger Tests (`test_logger.py`)

- ✅ Logger initialization
- ✅ Event logging (basic and full)
- ✅ Recent events retrieval
- ✅ Event limit enforcement
- ✅ Date range queries
- ✅ Device history retrieval
- ✅ Failed authentication tracking
- ✅ Old event cleanup
- ✅ Statistics generation
- ✅ CSV export
- ✅ EventAction enum validation

**Total: 12 tests**

### Configuration Tests (`test_config.py`)

- ✅ Configuration initialization
- ✅ Default config creation
- ✅ Getting existing keys
- ✅ Getting nonexistent keys with defaults
- ✅ Nested key access
- ✅ Setting values
- ✅ Setting nested values
- ✅ Creating new sections
- ✅ Save/load persistence
- ✅ is_enabled() helper
- ✅ set_enabled() helper
- ✅ get_timeout() helper
- ✅ set_timeout() helper with bounds checking
- ✅ Reset to defaults
- ✅ Config export/import
- ✅ Merging with defaults

**Total: 18 tests**

### Whitelist Tests (`test_whitelist.py`)

**DeviceWhitelist Tests:**
- ✅ Whitelist initialization
- ✅ Adding devices
- ✅ Serial number requirement
- ✅ Checking whitelist status
- ✅ Getting device information
- ✅ Removing devices
- ✅ Usage tracking
- ✅ Getting all devices
- ✅ Clearing whitelist
- ✅ Device count
- ✅ Updating device info
- ✅ Device search
- ✅ Whitelist export/import (replace and merge modes)

**DeviceInfo Tests:**
- ✅ Device path parsing
- ✅ Invalid path handling

**Total: 19 tests**

---

## Overall Test Statistics

- **Total Tests: 90**
- **Modules Tested: 5**
- **Test Success Rate: 100%**
- **Code Coverage: High (all core functions tested)**

---

## Running Tests

### Run All Tests

```bash
./run_tests.sh
# or
./run_tests.sh all
```

### Run Specific Module Tests

```bash
./run_tests.sh totp        # TOTP authentication tests
./run_tests.sh storage     # Secure storage tests
./run_tests.sh logger      # Logger tests
./run_tests.sh config      # Configuration tests
./run_tests.sh whitelist   # Whitelist tests
```

### Run with Coverage Report

```bash
./run_tests.sh coverage
```

This generates an HTML coverage report in `htmlcov/index.html`.

### Manual Test Execution

Using unittest directly:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
python -m unittest discover tests -v

# Run specific test file
python -m unittest tests.test_totp -v

# Run specific test class
python -m unittest tests.test_totp.TestTOTPAuthenticator -v

# Run specific test method
python -m unittest tests.test_totp.TestTOTPAuthenticator.test_verify_code_valid -v
```

---

## Test Environment Setup

### Prerequisites

The test suite requires:
- Python 3.13+
- Virtual environment with system site packages enabled
- Python dependencies: pyudev, pyotp, qrcode, cryptography, pillow

### Setup Instructions

```bash
# Create virtual environment (with system packages for dbus, gi)
python3 -m venv --system-site-packages .venv

# Install dependencies
.venv/bin/pip install pyudev pyotp qrcode[pil] cryptography pillow

# Run tests
.venv/bin/python -m unittest discover tests
```

The `run_tests.sh` script handles this setup automatically.

---

## Test Structure

```
tests/
├── __init__.py
├── test_totp.py          # TOTP authentication tests
├── test_storage.py       # Secure storage tests
├── test_logger.py        # Logger tests
├── test_config.py        # Configuration tests
├── test_whitelist.py     # Whitelist tests
└── README.md             # This file
```

---

## Test Patterns

### Temporary Directory Usage

Tests that require file I/O use temporary directories:

```python
def setUp(self):
    self.test_dir = Path(tempfile.mkdtemp())
    self.storage = SecureStorage(config_dir=self.test_dir)

def tearDown(self):
    if self.test_dir.exists():
        shutil.rmtree(self.test_dir)
```

This ensures tests are isolated and don't interfere with the actual system.

### Test Isolation

Each test:
- Creates its own temporary environment
- Cleans up after itself
- Doesn't depend on other tests
- Can run in any order

### Mocking

Currently, tests use real implementations where possible. Future improvements could include:
- Mocking file system operations for faster tests
- Mocking time for TOTP expiration tests
- Mocking D-Bus for daemon tests

---

## Continuous Integration

The test suite is designed to run in CI/CD environments:

```yaml
# Example GitHub Actions workflow
- name: Run Tests
  run: |
    python3 -m venv --system-site-packages .venv
    .venv/bin/pip install pyudev pyotp qrcode[pil] cryptography pillow
    .venv/bin/python -m unittest discover tests -v
```

---

## Known Limitations

### Tests Not Included

1. **D-Bus Service Tests**: Require D-Bus daemon and root privileges
2. **USB Monitor Tests**: Require actual USB devices or mocking
3. **Authorization Tests**: Require root access to /sys/bus/usb
4. **GUI Tests**: Require X display and GTK runtime
5. **Integration Tests**: End-to-end system testing

These require more complex setup and are candidates for future test expansion.

### Platform Dependencies

Tests are designed for:
- Linux (Ubuntu 25.04)
- Python 3.13+
- System packages: python3-gi, python3-dbus

---

## Test Development Guidelines

### Adding New Tests

1. **Create test file** in `tests/` directory
2. **Import unittest** and the module to test
3. **Create test class** inheriting from `unittest.TestCase`
4. **Implement setUp/tearDown** for fixtures
5. **Write test methods** starting with `test_`
6. **Use descriptive names** for test methods
7. **Add docstrings** explaining what each test does

### Test Naming Convention

```python
def test_{function}_{scenario}(self):
    """Test {description of what's being tested}."""
```

Examples:
- `test_verify_code_valid` - Test verifying a valid TOTP code
- `test_save_auth_data` - Test saving authentication data
- `test_get_timeout_bounds` - Test that timeout is bounded

### Assertions to Use

- `assertEqual(a, b)` - Check equality
- `assertNotEqual(a, b)` - Check inequality
- `assertTrue(x)` - Check if True
- `assertFalse(x)` - Check if False
- `assertIsNone(x)` - Check if None
- `assertIsNotNone(x)` - Check if not None
- `assertIn(a, b)` - Check if a in b
- `assertGreater(a, b)` - Check if a > b
- `assertRaises(Exception)` - Check if exception raised

---

## Debugging Failed Tests

### Verbose Output

```bash
python -m unittest tests.test_totp.TestTOTPAuthenticator.test_verify_code_valid -v
```

### Print Debugging

Add print statements in tests:

```python
def test_example(self):
    result = some_function()
    print(f"DEBUG: result = {result}")
    self.assertEqual(result, expected)
```

### Interactive Debugging

```bash
python -m pdb -m unittest tests.test_totp.TestTOTPAuthenticator.test_verify_code_valid
```

---

## Performance Benchmarks

Test execution times (approximate):
- `test_totp.py`: 0.003s
- `test_storage.py`: 0.385s (includes encryption operations)
- `test_logger.py`: 0.326s (includes database operations)
- `test_config.py`: 0.005s
- `test_whitelist.py`: 0.005s

**Total: ~0.8 seconds** for all 90 tests

---

## Future Test Enhancements

1. **Integration Tests**: End-to-end testing with mocked USB devices
2. **Performance Tests**: Benchmark TOTP verification speed
3. **Security Tests**: Penetration testing for authorization bypass
4. **Stress Tests**: High-volume event logging
5. **GUI Tests**: Automated UI testing with pytest-qt or similar
6. **Mock D-Bus**: Unit tests for daemon without real D-Bus
7. **Docker Tests**: Containerized test environment

---

## Contributing Tests

When contributing new features, please:

1. Write tests first (TDD approach)
2. Ensure all existing tests still pass
3. Achieve >80% code coverage for new code
4. Document test cases in this README
5. Follow existing test patterns

---

## Test Results

Last test run: All 90 tests passed ✓

```
----------------------------------------------------------------------
Ran 90 tests in 0.757s

OK
```

Coverage:
- Authentication module: 100%
- Storage module: 95%
- Logger module: 100%
- Config module: 100%
- Whitelist module: 100%
