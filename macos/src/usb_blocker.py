#!/usr/bin/env python3
"""
macOS helpers for blocking/unblocking USB devices.

Implements best-effort port control by toggling the "USB PortDisable"
IORegistry property exposed by IOUSBHostDevice. When a controller does not
honour that property, the code falls back to unmounting storage volumes using
diskutil (so non-storage peripherals may remain powered but data is blocked on
most modern Macs).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import subprocess

from . import path_setup  # noqa: F401


IOKit = ctypes.cdll.LoadLibrary(ctypes.util.find_library("IOKit"))
CoreFoundation = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))

CFStringCreateWithCString = CoreFoundation.CFStringCreateWithCString
CFStringCreateWithCString.restype = ctypes.c_void_p
CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]

CFNumberCreate = CoreFoundation.CFNumberCreate
CFNumberCreate.restype = ctypes.c_void_p
CFNumberCreate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]

CFDictionarySetValue = CoreFoundation.CFDictionarySetValue
CFDictionarySetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

CFRelease = CoreFoundation.CFRelease
CFRelease.argtypes = [ctypes.c_void_p]

IOServiceMatching = IOKit.IOServiceMatching
IOServiceMatching.restype = ctypes.c_void_p
IOServiceMatching.argtypes = [ctypes.c_char_p]

IOServiceGetMatchingService = IOKit.IOServiceGetMatchingService
IOServiceGetMatchingService.restype = ctypes.c_uint32
IOServiceGetMatchingService.argtypes = [ctypes.c_uint32, ctypes.c_void_p]

IORegistryEntrySetCFProperty = IOKit.IORegistryEntrySetCFProperty
IORegistryEntrySetCFProperty.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]

IOObjectRelease = IOKit.IOObjectRelease
IOObjectRelease.argtypes = [ctypes.c_uint32]

kCFStringEncodingUTF8 = 0x08000100
kCFNumberSInt32Type = 3
kCFBooleanTrue = ctypes.c_void_p.in_dll(CoreFoundation, "kCFBooleanTrue")
kCFBooleanFalse = ctypes.c_void_p.in_dll(CoreFoundation, "kCFBooleanFalse")


def _cf_string(value: str) -> ctypes.c_void_p:
    return CFStringCreateWithCString(None, value.encode("utf-8"), kCFStringEncodingUTF8)


def _cf_number(value: int) -> ctypes.c_void_p:
    c_value = ctypes.c_uint32(value)
    return CFNumberCreate(None, kCFNumberSInt32Type, ctypes.byref(c_value))


def _io_service_for_location(location_hex: str) -> ctypes.c_uint32:
    try:
        location_int = int(location_hex, 16)
    except ValueError:
        return ctypes.c_uint32(0)

    matching = IOServiceMatching(b"IOUSBHostDevice")
    if not matching:
        return ctypes.c_uint32(0)

    key = _cf_string("locationID")
    value = _cf_number(location_int)
    CFDictionarySetValue(matching, key, value)

    service = IOServiceGetMatchingService(0, matching)

    CFRelease(key)
    CFRelease(value)
    CFRelease(matching)

    return ctypes.c_uint32(service)


class MacDeviceBlocker:
    """Utility class for toggling USB authorization on macOS."""

    @staticmethod
    def block_device(location_id: str, bsd_name: str | None = None) -> bool:
        if MacDeviceBlocker._set_port_disabled(location_id, True):
            return True
        return MacDeviceBlocker._force_unmount(bsd_name)

    @staticmethod
    def allow_device(location_id: str) -> bool:
        return MacDeviceBlocker._set_port_disabled(location_id, False)

    @staticmethod
    def power_only(location_id: str) -> bool:
        # Same as block on macOS (data disabled, power usually remains)
        return MacDeviceBlocker.block_device(location_id)

    @staticmethod
    def _set_port_disabled(location_id: str, disabled: bool) -> bool:
        service = _io_service_for_location(location_id)
        if not service:
            return False

        key = _cf_string("USB PortDisable")
        value = kCFBooleanTrue if disabled else kCFBooleanFalse
        result = IORegistryEntrySetCFProperty(service, key, value) == 0
        CFRelease(key)
        IOObjectRelease(service)
        return result

    @staticmethod
    def _force_unmount(bsd_name: str | None) -> bool:
        if not bsd_name:
            return False

        device_path = f"/dev/{bsd_name}"
        try:
            result = subprocess.run(
                ["diskutil", "unmountDisk", "force", device_path],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return False

        return result.returncode == 0
