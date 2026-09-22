"""snapshot.json: the hand-over of live values (incl. the temperature) to the macOS widget."""

import json

from iox_stats import share
from iox_stats.share import SnapshotWriter, snapshot_payload


def test_payload_has_the_keys_the_widget_reads(snap):
    p = snapshot_payload(snap, 123.0)
    assert p["schema"] == share.SCHEMA and p["timestamp"] == 123.0
    assert p["cpu"] == 42.0 and p["temperature"] == 61.0 and p["memory"] == 63.0
    for key in ("swap", "disk", "ping_ms", "ping_ok", "ping_pending", "net_down_bps", "net_up_bps",
                "battery", "charging", "uptime_s", "app_version"):
        assert key in p


def test_widget_decodes_every_key():
    """The Swift struct (snake case converted to camel case) must declare every payload key."""
    from pathlib import Path
    import re

    text = (Path(__file__).resolve().parent.parent / "macos-widgets/Shared/SharedSnapshot.swift").read_text()
    fields = set(re.findall(r"^\s+var (\w+):", text, flags=re.M))
    from iox_stats.collectors import Snapshot

    for key in snapshot_payload(Snapshot(), 1.0):
        if key == "app_version":
            continue                                    # informational, not decoded
        camel = re.sub(r"_(\w)", lambda m: m.group(1).upper(), key)
        assert camel in fields, key


def test_writer_writes_atomically_and_throttles(tmp_path, snap):
    path = tmp_path / "sub" / "snapshot.json"
    w = SnapshotWriter(path, min_interval=2.0)
    assert w.write(snap, 100.0) is True
    assert json.loads(path.read_text())["cpu"] == 42.0
    snap.cpu_percent = 7
    assert w.write(snap, 100.5) is False                # too soon
    assert json.loads(path.read_text())["cpu"] == 42.0
    assert w.write(snap, 102.5) is True
    assert json.loads(path.read_text())["cpu"] == 7.0
    assert [p.name for p in path.parent.iterdir()] == ["snapshot.json"]       # no temp files left behind
    w.remove()
    assert not path.exists()
    w.remove()                                          # removing twice is fine


def test_writer_survives_unwritable_target(tmp_path, snap):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    w = SnapshotWriter(blocker / "snapshot.json")
    assert w.write(snap, 1.0) is False and w.failures == 1


def test_default_path_is_in_the_config_dir(tmp_path):
    assert share.snapshot_path().parent == tmp_path / "cfg"
    assert share.snapshot_path().name == "snapshot.json"
