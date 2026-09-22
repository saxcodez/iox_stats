"""Ring-buffer history for sparklines."""

from __future__ import annotations

from collections import deque
from typing import Deque, Dict, List, Optional

from .collectors import Snapshot


class History:
    def __init__(self, maxlen: int = 60):
        self.maxlen = maxlen
        self._data: Dict[str, Deque[Optional[float]]] = {}

    def push(self, snap: Snapshot) -> None:
        values = {
            "cpu": snap.cpu_percent,
            "ram": snap.ram_percent,
            "disk": snap.disk_percent,
            "net_down": snap.net_down_bps,
            "net_up": snap.net_up_bps,
            "ping": snap.ping_ms,
            "temp": snap.cpu_temp_c,
            "swap": snap.swap_percent,
            "battery": snap.battery_percent,
        }
        for key, val in values.items():
            self._data.setdefault(key, deque(maxlen=self.maxlen)).append(val)

    def series(self, key: str) -> List[Optional[float]]:
        return list(self._data.get(key, []))

    def __len__(self) -> int:
        return max((len(d) for d in self._data.values()), default=0)
