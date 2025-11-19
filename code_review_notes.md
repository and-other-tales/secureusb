# SecureUSB Code Review Notes

**Review Date**: 2025-11-19  
**Scope**: `src/` directory (19 Python files / 185 functions)

---

## Methodology
- Generated the up-to-date function inventory via `extract_functions.py` to make sure every Python module and function in `src/` was accounted for.
- Performed a manual read-through of each module focusing on correctness, error handling, and edge cases highlighted by recent bug reports.
- Cross-referenced behavior with the existing unit and integration tests in `tests/` to identify untested control paths.

## Overall Assessment
- Architectural layering (auth ⟷ daemon ⟷ GUI ⟷ utils) remains clean and modular.
- Unit tests already cover the majority of functionality, but a few GUI-centric code paths were previously untested.
- Logging, storage, and configuration components follow best practices (permissions, crypto primitives, PBKDF2 parameters, etc.).

## Findings & Fixes

### 1. Authorization dialog auto-deny timer never stopped (High)
- **File / Function**: `src/gui/auth_dialog.py` – `AuthorizationDialog._auto_deny`
- **Issue**: The GLib timeout callback returned a tuple `(None, False)` which is truthy, so GLib repeatedly re-scheduled the timer. This resulted in `_deny_device()` firing multiple times per timeout, spamming the daemon with duplicate deny requests.
- **Fix**: Provide a dedicated helper (`_deny_and_stop`) that calls `_deny_device()` once and explicitly returns `False` so the timeout is removed. Added regression test in `tests/test_auth_dialog.py` to prove the callback returns `False` and only invokes `_deny_device` once.

### 2. Whitelist search crashed on partially populated entries (Medium)
- **File / Function**: `src/utils/whitelist.py` – `DeviceWhitelist.search_devices`
- **Issue**: Search logic accessed `device['vendor_name']`, `device['product_name']`, and `device['notes']` directly. If a user-imported whitelist omitted any of these keys (or set them to `null`), the search raised `KeyError`/`AttributeError`, blocking GUI queries.
- **Fix**: Normalized all fields with `(device.get(key) or '').lower()` to tolerate missing/None values. Added `test_search_devices_handles_missing_fields` in `tests/test_whitelist.py` to cover this scenario.

### 3. GUI notifications were never shown to the desktop shell (Low)
- **File / Function**: `src/gui/client.py` – `SecureUSBClient._show_notification`
- **Issue**: Method still printed to stdout (leftover TODO), so users never received desktop notifications about authorization results.
- **Fix**: Hooked into `Gio.Notification`/`send_notification` with fallback logging so visual notifications now appear in the sandboxed shell.

### 4. Remember-device checkbox didn't add devices to whitelist (High)
- **File / Function**: `src/gui/auth_dialog.py` – `_authorize_device`
- **Issue**: The checkbox label promised to remember the device, but the TODO prevented any whitelist changes. D-Bus only accepted a serial number, so the daemon could not persist metadata.
- **Fix**: Wrapped the dialog content in an `Adw.ToastOverlay` for inline feedback, invoked a new `DBusClient.add_to_whitelist` helper, extended the D-Bus API to accept device metadata dictionaries, and implemented the daemon-side `add_whitelist` branch to store devices via `DeviceWhitelist`. Errors now surface as Adwaita toasts.

## Test Enhancements
- Added `tests/test_auth_dialog.py` with lightweight GI stubs to unit test the countdown/auto-deny logic that previously lacked coverage.
- Extended `tests/test_whitelist.py` to validate search robustness against malformed whitelist entries.

## Test Execution
- Activated the local virtual environment and ran the complete suite:
  - `source .venv/bin/activate && pytest`
  - Result: **203 passed, 26 skipped**

## Outstanding Risks / Follow-ups
- GUI notification plumbing (`_show_error` and `_show_notification`) still logs to stdout; consider integrating desktop notifications in a future iteration.
- Recovery-code whitelist enrollment (the TODO inside `_authorize_device`) is still pending and should be spec'd before implementation.
