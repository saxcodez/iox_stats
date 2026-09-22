"""CPU temperature providers.

* Linux / Windows(with sensors): ``psutil.sensors_temperatures()`` (handled in collectors.py).
* macOS has no public, unprivileged temperature API. IOX Stats therefore uses optional
  helper tools when they are installed (no sudo needed):

  - Apple Silicon (M1-M5): ``macmon``       ->  ``brew install macmon``
  - Intel Macs:            ``osx-cpu-temp`` ->  ``brew install osx-cpu-temp``

If none is available the temperature widget shows "n/a" together with the install hint.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from typing import Optional

from .helpers import find_tool

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

    def __init__(self, interval_ms: int = 2000):
        self.interval_ms = interval_ms
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
        if not self.tool:
            return
        self._stop.clear()
        target = self._run_macmon if self.tool == "macmon" else self._run_osx_cpu_temp
        self._thread = threading.Thread(target=target, name="iox-temp", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def _run_macmon(self) -> None:
        try:
            self._proc = subprocess.Popen(
                [self.path or "macmon", "pipe", "-i", str(self.interval_ms)],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            )
            assert self._proc.stdout is not None
            for line in self._proc.stdout:
                if self._stop.is_set():
                    break
                v = parse_macmon_line(line)
                if v is not None:
                    self.value = v
        except (OSError, AssertionError):
            self.value = None

    def _run_osx_cpu_temp(self) -> None:
        while not self._stop.is_set():
            try:
                out = subprocess.run([self.path or "osx-cpu-temp"], capture_output=True, text=True, timeout=5).stdout
                self.value = parse_osx_cpu_temp(out)
            except (OSError, subprocess.SubprocessError):
                self.value = None
            self._stop.wait(self.interval_ms / 1000.0)
