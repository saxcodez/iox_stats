import json

from iox_stats.collectors import Snapshot
from iox_stats.history import History
from iox_stats.metrics import CRIT, METRICS, NA, OK, WARN, tray_text, worst_level
from iox_stats.settings import Settings, config_dir


def test_levels(snap):
    assert METRICS["cpu"].level(snap) == OK
    snap.cpu_percent = 75
    assert METRICS["cpu"].level(snap) == WARN
    snap.cpu_percent = 95
    assert METRICS["cpu"].level(snap) == CRIT
    snap.cpu_temp_c = None
    assert METRICS["temp"].level(snap) == NA


def test_ping_states():
    s = Snapshot(timestamp=1)
    assert METRICS["ping"].text(s) == "..." and METRICS["ping"].level(s) == NA
    s.ping_pending = False
    assert METRICS["ping"].text(s) == "offline" and METRICS["ping"].level(s) == CRIT
    s.ping_ms = 150
    assert METRICS["ping"].text(s) == "150 ms" and METRICS["ping"].level(s) == WARN


def test_tray_text(snap):
    assert tray_text(snap, ["cpu", "temp", "ping"]) == "CPU 42%  T 61°C  Ping 18 ms"
    assert tray_text(snap, ["bogus", "ram"]) == "RAM 63%"


def test_worst_level(snap):
    assert worst_level(snap, ["cpu", "ping"]) == OK
    snap.ram_percent = 99
    assert worst_level(snap, ["cpu", "ram"]) == CRIT


def test_history_ring_buffer(snap):
    h = History(maxlen=5)
    for i in range(8):
        snap.cpu_percent = i
        h.push(snap)
    assert h.series("cpu") == [3, 4, 5, 6, 7]
    assert len(h) == 5 and h.series("nope") == []


def test_settings_roundtrip_and_sanitize(tmp_path):
    path = tmp_path / "s.json"
    s = Settings(theme="dark", interval_ms=10, tray_metrics=["ram", "nope", "cpu", "temp", "ping", "disk"])
    s.save(path)
    loaded = Settings.load(path)
    assert loaded.theme == "dark"
    assert loaded.interval_ms == 500  # clamped
    assert loaded.tray_metrics == ["ram", "cpu", "temp", "ping"]  # unknown dropped, max 4


def test_settings_corrupt_or_missing_file(tmp_path):
    assert Settings.load(tmp_path / "missing.json").theme == "system"
    bad = tmp_path / "bad.json"
    bad.write_text("{oops")
    assert Settings.load(bad).tray_metrics
    weird = tmp_path / "weird.json"
    weird.write_text(json.dumps({"theme": "neon", "tray_style": "x", "tray_metrics": [], "unknown": 1}))
    s = Settings.load(weird)
    assert s.theme == "system" and s.tray_style == "auto" and s.tray_metrics


def test_config_dir_override(tmp_path):
    assert str(config_dir()).endswith("cfg")
