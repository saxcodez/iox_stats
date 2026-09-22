import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("IOX_STATS_CONFIG_DIR", str(tmp_path / "cfg"))


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(["iox-test"])
    yield app


@pytest.fixture
def snap():
    from iox_stats.collectors import Snapshot

    return Snapshot(
        timestamp=1.0, cpu_percent=42.0, cpu_per_core=[10, 50, 90, 20], cpu_temp_c=61.0,
        ram_percent=63.0, ram_used=10 * 1024**3, ram_total=16 * 1024**3,
        disk_percent=71.0, disk_used=350 * 1024**3, disk_total=500 * 1024**3,
        net_down_bps=2.5e6, net_up_bps=3.1e5, ping_ms=18.0, ping_ok=True, ping_pending=False,
        battery_percent=54.0, battery_charging=False, uptime_s=90061,
    )
