"""Deterministic synthetic data for screenshots, docs and UI development (``--demo``)."""

from __future__ import annotations

import math
from typing import List

from .collectors import Snapshot


def demo_snapshots(n: int = 60) -> List[Snapshot]:
    out = []
    for i in range(n):
        wave = math.sin(i / 6.0)
        cores = [max(2.0, min(99.0, 35 + 30 * math.sin(i / 5.0 + k) + 8 * k)) for k in range(8)]
        out.append(Snapshot(
            timestamp=1_700_000_000 + i,
            cpu_percent=round(sum(cores) / len(cores), 1),
            cpu_per_core=cores,
            cpu_temp_c=52 + 9 * wave + i * 0.08,
            ram_percent=58 + 4 * math.sin(i / 11.0),
            ram_used=int(9.4 * 1024**3), ram_total=16 * 1024**3,
            disk_percent=64.0, disk_used=int(320 * 1024**3), disk_total=int(500 * 1024**3),
            net_down_bps=max(0.0, 1.8e6 + 1.5e6 * math.sin(i / 4.0) + (3e6 if i % 17 == 0 else 0)),
            net_up_bps=max(0.0, 2.2e5 + 1.2e5 * math.sin(i / 3.0 + 1)),
            ping_ms=18 + 6 * math.sin(i / 5.0) + (25 if i % 23 == 0 else 0),
            ping_ok=True, ping_pending=False,
            battery_percent=81.0, battery_charging=False, uptime_s=3 * 86400 + 5 * 3600,
        ))
    return out
