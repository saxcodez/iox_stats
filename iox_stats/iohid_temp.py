"""Apple Silicon CPU temperature straight from the IOHID sensor service - no helper tool, no sudo.

macOS exposes the SoC temperature sensors through ``IOHIDEventSystemClient`` (an IOKit API that is not documented
but has been stable since the M1 and is used by most system monitors). This module reads them with ``ctypes``.

Because a wrong ctypes call would crash the whole process, the app first runs ``python -m iox_stats.iohid_temp``
in a *child process* (``probe()``) and only reads in-process when that probe returned a plausible value.

Sensor names differ per chip; CPU die sensors are called ``PMU tdie1..n`` (M1-M4) and similar. We average the
die sensors; if a chip has none, we fall back to the SoC sensors.
"""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
from typing import Dict, List, Optional

_TEMPERATURE_EVENT = 15                       # kIOHIDEventTypeTemperature
_TEMPERATURE_FIELD = _TEMPERATURE_EVENT << 16  # IOHIDEventFieldBase(kIOHIDEventTypeTemperature)
_PAGE_APPLE_VENDOR = 0xFF00                   # kHIDPage_AppleVendor
_USAGE_TEMPERATURE_SENSOR = 5                 # kHIDUsage_AppleVendor_TemperatureSensor
_UTF8 = 0x08000100                            # kCFStringEncodingUTF8
_SINT32 = 3                                   # kCFNumberSInt32Type

_lib = None


def _load():
    global _lib
    if _lib is not None:
        return _lib
    iokit = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/IOKit.framework/IOKit")
    cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    vp, c_long, c_int = ctypes.c_void_p, ctypes.c_long, ctypes.c_int

    def fn(lib, name, restype, *argtypes):
        f = getattr(lib, name)
        f.restype = restype
        f.argtypes = list(argtypes)
        return f

    _lib = {
        "ClientCreate": fn(iokit, "IOHIDEventSystemClientCreate", vp, vp),
        "SetMatching": fn(iokit, "IOHIDEventSystemClientSetMatching", c_int, vp, vp),
        "CopyServices": fn(iokit, "IOHIDEventSystemClientCopyServices", vp, vp),
        "CopyProperty": fn(iokit, "IOHIDServiceClientCopyProperty", vp, vp, vp),
        "CopyEvent": fn(iokit, "IOHIDServiceClientCopyEvent", vp, vp, ctypes.c_int64, ctypes.c_int32, ctypes.c_int64),
        "GetFloat": fn(iokit, "IOHIDEventGetFloatValue", ctypes.c_double, vp, ctypes.c_int32),
        "NumberCreate": fn(cf, "CFNumberCreate", vp, vp, c_int, vp),
        "DictCreate": fn(cf, "CFDictionaryCreate", vp, vp, vp, vp, c_long, vp, vp),
        "StrCreate": fn(cf, "CFStringCreateWithCString", vp, vp, ctypes.c_char_p, ctypes.c_uint32),
        "StrGet": fn(cf, "CFStringGetCString", ctypes.c_bool, vp, ctypes.c_char_p, c_long, ctypes.c_uint32),
        "ArrCount": fn(cf, "CFArrayGetCount", c_long, vp),
        "ArrGet": fn(cf, "CFArrayGetValueAtIndex", vp, vp, c_long),
        "Release": fn(cf, "CFRelease", None, vp),
        "KeyCB": ctypes.addressof(ctypes.c_char.in_dll(cf, "kCFTypeDictionaryKeyCallBacks")),
        "ValCB": ctypes.addressof(ctypes.c_char.in_dll(cf, "kCFTypeDictionaryValueCallBacks")),
    }
    return _lib


def _cfstr(lib, text: str):
    return lib["StrCreate"](None, text.encode("utf-8"), _UTF8)


def _cfnum(lib, value: int):
    v = ctypes.c_int32(value)
    return lib["NumberCreate"](None, _SINT32, ctypes.byref(v))


def read_sensors() -> Dict[str, float]:
    """All temperature sensors as ``{name: celsius}``. Empty dict when unavailable. macOS only."""
    if sys.platform != "darwin":
        return {}
    lib = _load()
    keys = (ctypes.c_void_p * 2)(_cfstr(lib, "PrimaryUsagePage"), _cfstr(lib, "PrimaryUsage"))
    vals = (ctypes.c_void_p * 2)(_cfnum(lib, _PAGE_APPLE_VENDOR), _cfnum(lib, _USAGE_TEMPERATURE_SENSOR))
    matching = lib["DictCreate"](None, keys, vals, 2, lib["KeyCB"], lib["ValCB"])
    client = lib["ClientCreate"](None)
    result: Dict[str, float] = {}
    try:
        if not client or not matching:
            return result
        lib["SetMatching"](client, matching)
        services = lib["CopyServices"](client)
        if not services:
            return result
        product_key = _cfstr(lib, "Product")
        try:
            for i in range(lib["ArrCount"](services)):
                service = lib["ArrGet"](services, i)
                if not service:
                    continue
                name = "sensor%d" % i
                cf_name = lib["CopyProperty"](service, product_key)
                if cf_name:
                    buf = ctypes.create_string_buffer(128)
                    if lib["StrGet"](cf_name, buf, 128, _UTF8):
                        name = buf.value.decode("utf-8", "replace")
                    lib["Release"](cf_name)
                event = lib["CopyEvent"](service, _TEMPERATURE_EVENT, 0, 0)
                if event:
                    value = lib["GetFloat"](event, _TEMPERATURE_FIELD)
                    lib["Release"](event)
                    if 0.0 < value < 150.0:
                        result[name] = float(value)
        finally:
            lib["Release"](product_key)
            lib["Release"](services)
    finally:
        for obj in (*keys, *vals):
            if obj:
                lib["Release"](obj)
        if matching:
            lib["Release"](matching)
        if client:
            lib["Release"](client)
    return result


def cpu_temperature(sensors: Dict[str, float]) -> Optional[float]:
    """CPU temperature from the sensor list: mean of the CPU die sensors, else of the SoC sensors."""
    def pick(*needles: str) -> List[float]:
        return [v for k, v in sensors.items() if any(n in k.lower() for n in needles)]

    for group in (pick("tdie"), pick("pacc", "eacc", "cpu"), pick("soc", "tdev", "pmu")):
        if group:
            return round(sum(group) / len(group), 1)
    return None


def read_cpu_temperature() -> Optional[float]:
    try:
        return cpu_temperature(read_sensors())
    except (OSError, AttributeError, ValueError):
        return None


def probe(timeout: float = 8.0) -> Optional[float]:
    """Read once in a child process (a crash there cannot take the app down). Returns the value or None."""
    if sys.platform != "darwin" or getattr(sys, "frozen", False):
        return None
    try:
        out = subprocess.run([sys.executable, "-m", "iox_stats.iohid_temp", "--json"], capture_output=True,
                             text=True, timeout=timeout)
        if out.returncode != 0:
            return None
        return json.loads(out.stdout or "{}").get("cpu")
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


if __name__ == "__main__":
    sensors = read_sensors()
    if "--json" in sys.argv:
        print(json.dumps({"cpu": cpu_temperature(sensors), "sensors": sensors}))
    else:
        for k, v in sorted(sensors.items()):
            print(f"{k:32s} {v:6.1f} °C")
        print(f"CPU temperature: {cpu_temperature(sensors)}")
