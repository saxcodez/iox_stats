"""Cross-platform metric collectors (psutil based).

Every collector is defensive: on platforms or machines where a sensor does not
exist (e.g. temperatures on Windows/macOS without extra tools) the value is
``None`` and the UI shows "n/a" instead of crashing.
"""

from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import psutil

from .temperature import MacTempProvider


@dataclass
class Snapshot:
    """One point-in-time reading of all metrics."""

    timestamp: float = 0.0
    cpu_percent: float = 0.0
    cpu_per_core: list = field(default_factory=list)
    cpu_temp_c: Optional[float] = None
    ram_percent: float = 0.0
    ram_used: int = 0
    ram_total: int = 0
    swap_percent: float = 0.0
    disk_percent: float = 0.0
    disk_used: int = 0
    disk_total: int = 0
    net_down_bps: float = 0.0
    net_up_bps: float = 0.0
    ping_ms: Optional[float] = None  # None = unreachable / not measured yet
    ping_ok: bool = False
    ping_pending: bool = True  # no measurement finished yet
    battery_percent: Optional[float] = None
    battery_charging: Optional[bool] = None
    uptime_s: float = 0.0

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def _cpu_temperature() -> Optional[float]:
    """Best-effort CPU temperature in Celsius."""
    fn = getattr(psutil, "sensors_temperatures", None)
    if fn is None:
        return None
    try:
        temps = fn()
    except Exception:
        return None
    if not temps:
        return None
    preferred = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "cpu-thermal", "acpitz")
    for name in preferred:
        entries = temps.get(name)
        if entries:
            vals = [e.current for e in entries if e.current is not None]
            if vals:
                return float(max(vals))
    for entries in temps.values():
        vals = [e.current for e in entries if e.current is not None]
        if vals:
            return float(max(vals))
    return None


def _disk_root() -> str:
    import os

    if os.name == "nt":
        return os.environ.get("SystemDrive", "C:") + "\\"
    return "/"


def measure_ping(host: str = "1.1.1.1", port: int = 443, timeout: float = 1.5) -> Optional[float]:
    """TCP connect latency in ms (works without admin rights on every OS)."""
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError:
        return None
    return (time.perf_counter() - start) * 1000.0


class Collector:
    """Collects a :class:`Snapshot`; ping runs in a background thread so the UI never blocks."""

    def __init__(self, ping_host: str = "1.1.1.1", ping_port: int = 443, ping_interval: float = 3.0):
        self.ping_host = ping_host
        self.ping_port = ping_port
        self.ping_interval = ping_interval
        self._last_net = None
        self._last_net_t = 0.0
        self._ping_ms: Optional[float] = None
        self._ping_ok = False
        self._ping_pending = True
        self._ping_thread: Optional[threading.Thread] = None
        self._ping_stop = threading.Event()
        self._mac_temp = MacTempProvider()
        psutil.cpu_percent(None)  # prime the counter
        psutil.cpu_percent(None, percpu=True)

    # -- ping thread ---------------------------------------------------------
    def start(self) -> None:
        """Start background workers (ping thread and, on macOS, the temperature helper)."""
        self.start_ping()
        self._mac_temp.start()

    def refresh_helpers(self) -> Optional[str]:
        """Look for a temperature helper again (after it was installed) and start it. Returns its name."""
        return self._mac_temp.restart()

    def start_ping(self) -> None:
        if self._ping_thread and self._ping_thread.is_alive():
            return
        self._ping_stop.clear()
        self._ping_thread = threading.Thread(target=self._ping_loop, name="iox-ping", daemon=True)
        self._ping_thread.start()

    def stop(self) -> None:
        self._ping_stop.set()
        self._mac_temp.stop()

    def _ping_loop(self) -> None:
        while not self._ping_stop.is_set():
            ms = measure_ping(self.ping_host, self.ping_port)
            self._ping_ms, self._ping_ok, self._ping_pending = ms, ms is not None, False
            self._ping_stop.wait(self.ping_interval)

    def set_ping_result(self, ms: Optional[float]) -> None:
        """Inject a ping result (used by tests)."""
        self._ping_ms, self._ping_ok, self._ping_pending = ms, ms is not None, False

    # -- sampling ------------------------------------------------------------
    def sample(self) -> Snapshot:
        now = time.time()
        vm = psutil.virtual_memory()
        try:
            sw = psutil.swap_memory().percent
        except Exception:
            sw = 0.0
        try:
            du = psutil.disk_usage(_disk_root())
            disk = (du.percent, du.used, du.total)
        except Exception:
            disk = (0.0, 0, 0)

        down = up = 0.0
        try:
            io = psutil.net_io_counters()
            t = time.monotonic()
            if self._last_net is not None and t > self._last_net_t:
                dt = t - self._last_net_t
                down = max(0.0, (io.bytes_recv - self._last_net.bytes_recv) / dt)
                up = max(0.0, (io.bytes_sent - self._last_net.bytes_sent) / dt)
            self._last_net, self._last_net_t = io, t
        except Exception:
            pass

        batt_p = batt_c = None
        try:
            b = psutil.sensors_battery()
            if b is not None:
                batt_p, batt_c = float(b.percent), bool(b.power_plugged)
        except Exception:
            pass

        temp = _cpu_temperature()
        if temp is None:
            temp = self._mac_temp.value

        return Snapshot(
            timestamp=now,
            cpu_percent=psutil.cpu_percent(None),
            cpu_per_core=psutil.cpu_percent(None, percpu=True),
            cpu_temp_c=temp,
            ram_percent=vm.percent,
            ram_used=vm.used,
            ram_total=vm.total,
            swap_percent=sw,
            disk_percent=disk[0],
            disk_used=disk[1],
            disk_total=disk[2],
            net_down_bps=down,
            net_up_bps=up,
            ping_ms=self._ping_ms,
            ping_ok=self._ping_ok,
            ping_pending=self._ping_pending,
            battery_percent=batt_p,
            battery_charging=batt_c,
            uptime_s=max(0.0, now - psutil.boot_time()),
        )


# -- formatting helpers ------------------------------------------------------
def fmt_bytes(n: float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def fmt_rate(bps: float) -> str:
    return fmt_bytes(bps) + "/s"


def fmt_uptime(seconds: float) -> str:
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m = s // 60
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def split_bytes(n: float):
    """Return (number, unit) so UIs can draw the unit smaller, e.g. ("2.9", "MB")."""
    text = fmt_bytes(n)
    num, _, unit = text.partition(" ")
    if "." in num and float(num) >= 100:
        num = f"{float(num):.0f}"      # 180.0 GB -> 180 GB
    return num, unit


def split_rate(bps: float):
    num, unit = split_bytes(bps)
    return num, unit + "/s"


def uptime_parts(seconds: float):
    """[(number, unit), ...] for the uptime hero text: 3d 5h / 5h 7m / 12m."""
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m = s // 60
    if d:
        return [(str(d), "d"), (str(h), "h")]
    if h:
        return [(str(h), "h"), (str(m), "m")]
    return [(str(m), "m")]
