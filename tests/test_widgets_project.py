"""The macOS widget project (Swift) cannot run here, so these tests guard what can be checked from Python:
version agreement, layout limits in sync with the window, files present, balanced brackets."""

import re
from pathlib import Path

import pytest

from iox_stats import __version__
from iox_stats.layout import CAPACITY
from iox_stats.metrics import METRICS

ROOT = Path(__file__).resolve().parent.parent
WIDGETS = ROOT / "macos-widgets"
SWIFT_FILES = sorted(WIDGETS.rglob("*.swift"))


def test_project_files_exist():
    for rel in ("project.yml", "README.md", "App/IOXStatsApp.swift", "App/ContentView.swift", "App/App.entitlements",
                "Widget/StatsWidget.swift", "Widget/Layout.swift", "Widget/Snapshot.swift", "Widget/Collector.swift",
                "Widget/Views.swift", "Widget/Widget.entitlements", "Shared/SharedSnapshot.swift", "Widget/SharedSnapshot+System.swift",
                "App/RefreshDriver.swift", "App/OnboardingView.swift", "App/SettingsView.swift"):
        assert (WIDGETS / rel).is_file(), rel


def test_widget_version_matches_package_version():
    spec = (WIDGETS / "project.yml").read_text(encoding="utf-8")
    m = re.search(r'MARKETING_VERSION:\s*"([^"]+)"', spec)
    assert m and m.group(1) == __version__


def test_swift_capacities_match_python_layout():
    text = (WIDGETS / "Widget" / "Layout.swift").read_text(encoding="utf-8")
    small = dict(re.findall(r"\(\.systemSmall, \.(\w+)\): return (\d+)", text))
    other = dict(re.findall(r"\(_, \.(\w+)\): return (\d+)", text))
    for style in ("rings", "bars", "numbers"):
        assert int(small[style]) == CAPACITY[("small", style)], style
        assert int(other[style]) == CAPACITY[("medium", style)], style


def test_swift_metric_choices_cover_python_values():
    text = (WIDGETS / "Widget" / "Layout.swift").read_text(encoding="utf-8")
    cases = set(re.search(r"case empty, ([\w, ]+)\n", text).group(1).replace(" ", "").split(","))
    # the CPU temperature comes from the Python app (snapshot.json); the thermal state is the fallback
    expected = {"cpu", "temperature", "memory", "swap", "disk", "ping", "download", "upload", "battery", "uptime", "thermal"}
    assert cases == expected
    python_ids = set(METRICS)
    assert {"cpu", "ram", "swap", "disk", "ping", "net_down", "net_up", "battery", "uptime"} <= python_ids


def _strip(source: str) -> str:
    """Drop comments and string contents in one pass (so "https://..." in a string is not taken for a comment)."""
    token = re.compile(r'"(?:\\.|[^"\\\n])*"|//[^\n]*|/\*.*?\*/', re.S)
    return token.sub(lambda m: '""' if m.group(0).startswith('"') else "", source)


@pytest.mark.parametrize("path", SWIFT_FILES, ids=lambda p: p.name)
def test_swift_brackets_are_balanced(path):
    """Cheap guard against truncated or mangled files (a real compile happens in CI on macOS)."""
    stack, pairs = [], {")": "(", "]": "[", "}": "{"}
    for ch in _strip(path.read_text(encoding="utf-8")):
        if ch in "([{":
            stack.append(ch)
        elif ch in pairs:
            assert stack and stack.pop() == pairs[ch], f"unbalanced {ch!r} in {path.name}"
    assert not stack, f"unclosed {stack} in {path.name}"


def test_exactly_one_entry_point_and_two_targets():
    mains = [p.name for p in SWIFT_FILES if "@main" in p.read_text(encoding="utf-8")]
    assert sorted(mains) == ["IOXStatsApp.swift", "StatsWidget.swift"]      # app + widget bundle


def test_widget_is_sandboxed_with_network_client():
    ent = (WIDGETS / "Widget" / "Widget.entitlements").read_text(encoding="utf-8")
    assert "com.apple.security.app-sandbox" in ent and "com.apple.security.network.client" in ent


def test_widget_bundle_id_extends_app_bundle_id():
    spec = (WIDGETS / "project.yml").read_text(encoding="utf-8")
    ids = re.findall(r"PRODUCT_BUNDLE_IDENTIFIER:\s*(\S+)", spec)
    assert len(ids) == 2 and ids[1].startswith(ids[0] + ".")


def test_entitlements_are_defined_in_project_yml_and_match_the_files():
    """XcodeGen rewrites .entitlements files from project.yml on every generate. If the properties are missing
    there, the signed widget loses its sandbox and macOS rejects it ("plug-ins must be sandboxed", v0.9.0)."""
    import plistlib

    yaml = pytest.importorskip("yaml")
    spec = yaml.safe_load((WIDGETS / "project.yml").read_text(encoding="utf-8"))
    for target, rel in (("IOXStats", "App/App.entitlements"), ("IOXStatsWidgets", "Widget/Widget.entitlements")):
        ent = spec["targets"][target]["entitlements"]
        assert ent["path"] == rel
        props = ent.get("properties") or {}
        assert props.get("com.apple.security.app-sandbox") is True, target
        with open(WIDGETS / rel, "rb") as fh:
            assert plistlib.load(fh) == props, f"{rel} differs from project.yml"
    widget = spec["targets"]["IOXStatsWidgets"]["entitlements"]["properties"]
    assert widget.get("com.apple.security.network.client") is True          # ping
