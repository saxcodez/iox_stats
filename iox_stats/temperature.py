"""CPU temperature providers.

* Linux / Windows(with sensors): ``psutil.sensors_temperatures()`` (handled in collectors.py).
* macOS has no public, unprivileged temperature API. IOX Stats therefore uses optional
  helper tools when they are installed (no sudo needed):

  - Apple Silicon (M1-M5): ``macmon``       ->  ``brew install macmon``
  - Intel Macs:            ``osx-cpu-temp`` ->  ``brew install osx-cpu-temp``

  - Apple Silicon without a helper (or when the helper reports nothing): the IOHID sensor service, read
    directly (``iohid_temp.py``) after a crash-safe probe in a child process.

If nothing works the temperature widget shows "n/a". Every step is logged (``--diagnose`` shows it too).
"""

from __future__ import annotations

import json
import logging
import platform
import re
import subprocess
import sys
import threading
from typing import Callable, Optional

from . import iohid_temp
from .helpers import find_tool

log = logging.getLogger("iox_stats.temperature")
HELPER_TIMEOUT_S = 12.0        # no valid value from the helper within this time -> fall back to IOHID

MAC_HINT = "brew install macmon"


def parse_macmon_line(line: str) -> Optional[float]:
    """Extract ``temp.cpu_temp_avg`` from one line of ``macmon pipe`` JSON output."""
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
        val = data["temp"]["cpu_temp_avg"]
        val = float(val)
    except (ValueError, KeyError, TypeError):
        return None
    return val if 0.0 < val < 150.0 else None


def parse_osx_cpu_temp(text: str) -> Optional[float]:
    """Parse ``osx-cpu-temp`` output such as ``61.2°C``."""
    m = re.search(r"(-?\d+(?:[.,]\d+)?)\s*°?\s*C", text)
    if not m:
        return None
    val = float(m.group(1).replace(",", "."))
    return val if 0.0 < val < 150.0 else None


class MacTempProvider:
    """Background reader for macOS temperature helper tools. Safe no-op elsewhere."""

    def __init__(self, interval_ms: int = 2000, iohid_probe: Callable[[], Optional[float]] = iohid_temp.probe,
                 iohid_read: Callable[[], Optional[float]] = iohid_temp.read_cpu_temperature):
        self.interval_ms = interval_ms
        self._iohid_probe_fn = iohid_probe
        self._iohid_read = iohid_read
        self._iohid_ok: Optional[bool] = None
        self.last_error: Optional[str] = None
        self.value: Optional[float] = None
        self.tool: Optional[str] = None
        self.path: Optional[str] = None
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    @staticmethod
    def supported() -> bool:
        return sys.platform == "darwin"

    def detect(self) -> Optional[str]:
        """Name of the installed helper. Also finds Homebrew tools when PATH is minimal (start at login)."""
        for tool in ("macmon", "osx-cpu-temp"):
            path = find_tool(tool)
            if path:
                self.path = path
                return tool
        return None

    def restart(self) -> Optional[str]:
        """Stop, look for a helper again (e.g. right after it was installed) and start it."""
        self.stop()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
        self._thread = None
        self._proc = None
        self.value = None
        self.start()
        return self.tool

    def start(self) -> None:
        if not self.supported() or (self._thread and self._thread.is_alive()):
            return
        self.tool = self.detect()
        self._stop.clear()
        if not self.tool:
            # nothing installed: Apple Silicon can still be read directly (probe runs in the thread, not the UI)
            target = self._start_iohid_or_give_up
        else:
            log.info("temperature helper: %s (%s)", self.tool, self.path)
            target = self._run_macmon if self.tool == "macmon" else self._run_osx_cpu_temp
        self._thread = threading.Thread(target=target, name="iox-temp", daemon=True)
        self._thread.start()

    # -- IOHID fallback ------------------------------------------------------
    def iohid_available(self) -> bool:
        """Crash-safe check (child process) whether the IOHID sensors can be read. Cached."""
        if self._iohid_ok is None:
            if platform.machine().lower() not in ("arm64", "aarch64"):
                self._iohid_ok = False
            else:
                value = self._iohid_probe_fn()
                self._iohid_ok = value is not None
                log.info("IOHID sensor probe: %s", value if value is not None else "no value")
        return self._iohid_ok

    def _start_iohid_or_give_up(self) -> None:
        if self.iohid_available():
            self.tool = "iohid"
            self._run_iohid()
        else:
            self.last_error = "no temperature helper and no IOHID sensors"
            log.warning("no CPU temperature source: install macmon (Apple Silicon) or osx-cpu-temp (Intel)")

    def _run_iohid(self) -> None:
        log.info("reading the CPU temperature from the IOHID sensors")
        while not self._stop.is_set():
            try:
                self.value = self._iohid_read()
            except Exception as exc:          # never let the sensor thread die silently
                self.last_error = f"IOHID: {exc}"
                log.exception("IOHID read failed")
                self.value = None
            self._stop.wait(self.interval_ms / 1000.0)

    def _helper_failed(self, why: str) -> None:
        """The helper gave no usable value: log why and switch to IOHID if possible."""
        self.last_error = why
        log.warning("%s gave no CPU temperature: %s", self.tool, why)
        if not self._stop.is_set() and self.iohid_available():
            self.tool = "iohid"
            self._run_iohid()

    def stop(self) -> None:
        self._stop.set()
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def _run_macmon(self) -> None:
        got_value = False
        first_line = ""
        try:
            proc = subprocess.Popen(
                [self.path or "macmon", "pipe", "-i", str(self.interval_ms)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self._proc = proc
            # watchdog: a helper that prints nothing usable is stopped, so we can fall back
            watchdog = threading.Timer(HELPER_TIMEOUT_S, lambda: None if got_value else proc.terminate())
            watchdog.daemon = True
            watchdog.start()
            assert proc.stdout is not None
            for line in proc.stdout:
                if self._stop.is_set():
                    break
                first_line = first_line or line.strip()[:300]
                v = parse_macmon_line(line)
                if v is not None:
                    if not got_value:
                        log.info("macmon: first CPU temperature %.1f °C", v)
                    got_value = True
                    self.value = v
            watchdog.cancel()
        except (OSError, AssertionError) as exc:
            self.value = None
            if not self._stop.is_set():
                self._helper_failed(f"could not run macmon: {exc}")
            return
        if self._stop.is_set():
            return
        self.value = None
        err = ""
        try:
            proc.wait(timeout=2)
            err = (proc.stderr.read() if proc.stderr else "").strip()[-400:]
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
        detail = f"exit code {proc.returncode}"
        if err:
            detail += f", stderr: {err}"
        if first_line and not got_value:
            detail += f", output: {first_line}"
        self._helper_failed(detail if not got_value else f"macmon stopped ({detail})")

    def _run_osx_cpu_temp(self) -> None:
        failures = 0
        while not self._stop.is_set():
            out = ""
            try:
                out = subprocess.run([self.path or "osx-cpu-temp"], capture_output=True, text=True, timeout=5).stdout
                self.value = parse_osx_cpu_temp(out)
            except (OSError, subprocess.SubprocessError) as exc:
                out = str(exc)
                self.value = None
            if self.value is None:
                failures += 1
                if failures == 3:
                    self._helper_failed(f"output: {out.strip()[:200]!r}")
                    return
            else:
                failures = 0
            self._stop.wait(self.interval_ms / 1000.0)
