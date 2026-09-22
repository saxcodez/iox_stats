"""Share the live values with the macOS widget (macos-widgets/).

The widget lives in a sandbox and cannot read the CPU temperature or run helper tools. The Python app can, and it
samples every second anyway, so it writes its newest values to a small JSON file that the widget reads:

    ~/Library/Application Support/IOXStats/snapshot.json

The file is replaced atomically, so the widget never sees half a file. Only numbers are written (no names, no
network addresses). Switch it off with ``"share_with_widgets": false`` in settings.json.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from . import __version__
from .collectors import Snapshot
from .settings import config_dir

SNAPSHOT_NAME = "snapshot.json"
SCHEMA = 1


def snapshot_path() -> Path:
    return config_dir() / SNAPSHOT_NAME


def snapshot_payload(snap: Snapshot, now: Optional[float] = None) -> Dict[str, Any]:
    """The JSON document the widget reads. Keys are documented in macos-widgets/Shared/SharedSnapshot.swift."""
    return {
        "schema": SCHEMA,
        "app_version": __version__,
        "timestamp": now if now is not None else time.time(),
        "cpu": snap.cpu_percent,
        "temperature": snap.cpu_temp_c,
        "memory": snap.ram_percent,
        "swap": snap.swap_percent,
        "disk": snap.disk_percent,
        "ping_ms": snap.ping_ms,
        "ping_ok": bool(snap.ping_ok),
        "ping_pending": bool(snap.ping_pending),
        "net_down_bps": snap.net_down_bps,
        "net_up_bps": snap.net_up_bps,
        "battery": snap.battery_percent,
        "charging": bool(snap.battery_charging) if snap.battery_charging is not None else False,
        "uptime_s": snap.uptime_s,
    }


class SnapshotWriter:
    """Writes the snapshot file at most every ``min_interval`` seconds."""

    def __init__(self, path: Optional[Path] = None, min_interval: float = 2.0):
        self.path = path
        self.min_interval = min_interval
        self._last_write = float("-inf")
        self.failures = 0

    def write(self, snap: Snapshot, now: Optional[float] = None) -> bool:
        """Write ``snap`` unless the last write was too recent. Returns True when a file was written."""
        t = now if now is not None else time.time()
        if t - self._last_write < self.min_interval:
            return False
        target = self.path or snapshot_path()
        payload = json.dumps(snapshot_payload(snap, t), separators=(",", ":"))
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".snapshot-", suffix=".tmp", dir=str(target.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(payload)
                os.replace(tmp, target)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except OSError:
            self.failures += 1
            return False
        self._last_write = t
        return True

    def remove(self) -> None:
        """Delete the file (on quit), so the widget falls back to its own measurements."""
        try:
            (self.path or snapshot_path()).unlink()
        except OSError:
            pass


def enabled_by_default() -> bool:
    """Only macOS has the widget; other systems do not need the file."""
    return sys.platform == "darwin" or bool(os.environ.get("IOX_STATS_SHARE"))
