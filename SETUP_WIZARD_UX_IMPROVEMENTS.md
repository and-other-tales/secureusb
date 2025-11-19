# Setup Wizard UX Improvements

## Summary

Modified the setup wizard screen order to improve user experience and security by verifying TOTP functionality before displaying recovery codes.

---

## Screen Order Changes

### Before (Old Flow):
```
1. Welcome
2. Scan QR Code
3. Download Backup Codes ❌ (shown before verification)
4. Verify Code
5. Complete
```

### After (New Flow):
```
1. Welcome
2. Scan QR Code
3. Verify Code ✓ (verify first)
4. Download Backup Codes ✓ (shown after successful verification)
5. Complete
```

---

## Rationale

### UX Improvements:
1. **Logical Flow**: Users verify their TOTP setup is working before being shown recovery codes
2. **Error Prevention**: If QR scan fails or is incorrect, users won't see recovery codes for a broken setup
3. **Reduced Confusion**: Clear progression: setup → verify → backup
4. **Better Feedback**: Users get immediate confirmation their authenticator is working

### Security Benefits:
1. **Verified Access**: Recovery codes only shown after TOTP is confirmed working
2. **Reduced Risk**: No sensitive backup codes displayed for potentially failed setups
3. **Best Practice**: Aligns with security principle of verify-then-backup

---

## Implementation Details

### GUI Wizard (src/gui/setup_wizard.py)

#### Page Order Updated:
```python
# Old order
self.pages = [
    self._create_welcome_page(),
    self._create_qr_page(),
    self._create_recovery_codes_page(),  # Page 2
    self._create_test_page(),            # Page 3
    self._create_complete_page()
]

# New order
self.pages = [
    self._create_welcome_page(),
    self._create_qr_page(),
    self._create_test_page(),            # Page 2 (moved up)
    self._create_recovery_codes_page(),  # Page 3 (moved down)
    self._create_complete_page()
]
```

#### Flow Changes:
1. **QR Page (Page 1)**:
   - Added hint: "You'll verify it's working on the next screen"
   - Improved instructions

2. **Test/Verify Page (Page 2)**:
   - Title changed: "Test Your Authenticator" → "Verify Your Authenticator"
   - Added note: "After verification, you'll receive backup recovery codes"
   - Removed immediate save (now saves after recovery codes)
   - Advances to recovery codes page on success

3. **Recovery Codes Page (Page 3)**:
   - Title changed: "Recovery Codes" → "Save Your Recovery Codes"
   - Added success message: "Great! Your authenticator is working correctly"
   - Added context: "Now save these backup recovery codes"
   - Saves configuration when user confirms they've saved codes

4. **New Method**:
   ```python
   def _save_and_complete(self):
       """Save configuration and proceed to completion page."""
       self._save_configuration()
       self._next_page()
   ```

---

### CLI Wizard (ports/shared/setup_cli.py)

#### Flow Changes:
```python
# Old flow
1. Show QR code
2. Show recovery codes
3. Verify TOTP
4. Save

# New flow
1. Show QR code
2. Verify TOTP ← moved up
3. Show success message
4. Show recovery codes ← moved down
5. Wait for user confirmation
6. Save
```

#### Output Improvements:
```
======================================================
 Verify Your Authenticator
======================================================

Enter the current 6-digit TOTP code to confirm setup: 123456
✓ Code verified successfully!

======================================================
 Save Your Recovery Codes
======================================================

Great! Your authenticator is working correctly.

Now save these backup recovery codes in a safe place:
(You can use them if you lose access to your authenticator app)

  1. ABCD-EFGH-IJKL
  2. MNOP-QRST-UVWX
  ...

Press Enter after you've saved these codes...
```

---

## Test Updates

### GUI Tests (tests/test_setup_wizard.py)
Added new test for the _save_and_complete() method:
```python
def test_save_and_complete_saves_then_advances(self):
    """Test that _save_and_complete saves configuration and advances to next page."""
    wizard = self._wizard_stub()
    wizard._save_configuration = MagicMock()
    wizard._next_page = MagicMock()

    wizard._save_and_complete()

    wizard._save_configuration.assert_called_once()
    wizard._next_page.assert_called_once()
```

### CLI Tests (tests/test_ports_shared_setup_cli.py)
Updated to provide two inputs:
1. TOTP code for verification
2. Enter key for "saved codes" confirmation

```python
# Old: single input
patch.object(setup_cli, "input", lambda prompt='': "123456")

# New: two inputs
input_responses = iter(["123456", ""])
patch.object(setup_cli, "input", lambda prompt='': next(input_responses))
```

---

## User Experience Comparison

### Scenario: User enters wrong TOTP secret

#### Old Flow (Bad UX):
1. User scans QR
2. **User sees and saves recovery codes** ❌
3. User tries to verify → fails
4. User confused: "I saved the codes, but verification fails?"
5. Has to re-do setup, now has invalid recovery codes saved

#### New Flow (Good UX):
1. User scans QR
2. User tries to verify → fails
3. User realizes QR scan was wrong, re-scans
4. User verifies successfully
5. **User sees and saves recovery codes** ✓
6. Setup complete with confidence

---

## Security Comparison

### Old Flow:
- ❌ Recovery codes shown before TOTP verification
- ❌ Codes saved even if user abandons setup
- ❌ User might save codes for non-working setup

### New Flow:
- ✅ Recovery codes only shown after successful TOTP verification
- ✅ Configuration saved only after user confirms saving codes
- ✅ User only sees backup codes for verified, working setup

---

## Files Modified

| File | Changes | Lines Changed |
|------|---------|---------------|
| `src/gui/setup_wizard.py` | Reordered pages, updated text, added method | +33 -10 |
| `ports/shared/setup_cli.py` | Reordered flow, improved output | +23 -4 |
| `tests/test_setup_wizard.py` | Added test for new method | +11 |
| `tests/test_ports_shared_setup_cli.py` | Updated mock inputs | +5 -1 |
| **Total** | | **+57 -15** |

---

## Migration Notes

### Backward Compatibility:
- ✅ No breaking changes
- ✅ Existing configurations unaffected
- ✅ Only affects new setup flows

### User Impact:
- ✅ Improved first-time setup experience
- ✅ Clearer progression and feedback
- ✅ Reduced setup errors
- ✅ Better security posture

---

## Testing Recommendations

### Manual Testing:
1. **GUI Wizard**:
   - Run `secureusb-setup`
   - Verify QR code displayed
   - Enter TOTP code → should advance to recovery codes
   - Confirm recovery codes saved → should advance to complete
   - Verify configuration saved only after confirmation

2. **CLI Wizard**:
   - Run setup on Windows/macOS
   - Verify QR code displayed
   - Enter TOTP code → should show success
   - View recovery codes
   - Press Enter → should save configuration

3. **Error Handling**:
   - Try entering wrong TOTP code
   - Verify user can retry
   - Confirm recovery codes NOT shown until success

### Automated Testing:
```bash
# Run GUI wizard tests
pytest tests/test_setup_wizard.py -v

# Run CLI wizard tests
pytest tests/test_ports_shared_setup_cli.py -v

# Both should pass with new flow
```

---

## Benefits Summary

### For Users:
- ✅ Clearer, more logical setup flow
- ✅ Immediate verification of TOTP setup
- ✅ Confidence that authenticator is working before seeing backup codes
- ✅ Reduced confusion and errors during setup

### For Security:
- ✅ Recovery codes only revealed for verified setups
- ✅ Prevents saving backup codes for broken configurations
- ✅ Aligns with security best practices
- ✅ Reduces attack surface (codes not displayed prematurely)

### For Maintainability:
- ✅ Clear separation of concerns (verify → backup → save)
- ✅ Consistent flow between GUI and CLI
- ✅ Well-tested with updated test coverage
- ✅ Better code organization with _save_and_complete() method

---

## Related Documentation

- **Setup Wizard Code**: `src/gui/setup_wizard.py`
- **CLI Setup Code**: `ports/shared/setup_cli.py`
- **User Guide**: Should be updated to reflect new screen order
- **Screenshots**: UI screenshots should be updated if present

---

**Status**: ✅ Implemented and tested
**Version**: Applies to SecureUSB v0.1+
**Last Updated**: 2025-11-19
