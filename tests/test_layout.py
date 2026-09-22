"""Widget layout model: styles, capacities, limits, persistence (pure logic, no Qt)."""

import json

import pytest

from iox_stats.layout import (CAPACITY, DEFAULT_LAYOUT, MAX_WIDGETS, PRESETS, SIZES, STYLES, LayoutStore,
                              WidgetConfig, W, capacity, layout_to_raw, sanitize_layout)
from iox_stats.metrics import METRICS
from iox_stats.settings import Settings


class _Mem:
    """Minimal settings stand-in that counts saves."""

    def __init__(self, widgets=None):
        self.widgets = widgets if widgets is not None else layout_to_raw(DEFAULT_LAYOUT)
        self.saves = 0

    def save(self):
        self.saves += 1


def test_capacity_table_is_complete_and_sensible():
    assert set(CAPACITY) == {(s, st) for s in SIZES for st in STYLES}
    for style in STYLES:                       # a medium widget always fits at least as much as a small one
        assert capacity("medium", style) >= capacity("small", style)
    assert capacity("small", "detail") == 1


def test_from_dict_repairs_garbage():
    assert WidgetConfig.from_dict("nope") == WidgetConfig()
    cfg = WidgetConfig.from_dict({"size": "huge", "style": "sparkles", "metrics": ["cpu", "cpu", "bogus", 5]})
    assert (cfg.size, cfg.style, cfg.metrics) == ("small", "detail", ("cpu",))
    assert WidgetConfig.from_dict({"metrics": []}).metrics == ("cpu",)        # never empty


def test_from_dict_truncates_to_capacity():
    cfg = WidgetConfig.from_dict({"size": "small", "style": "rings", "metrics": ["cpu", "ram", "disk", "temp"]})
    assert cfg.metrics == ("cpu", "ram")


def test_size_and_style_changes_truncate_values():
    big = W("medium", "numbers", "cpu", "ram", "temp", "disk", "ping", "uptime")
    assert len(big.metrics) == 6
    assert len(big.with_size("small").metrics) == 3
    assert len(big.with_style("rings").metrics) == 4
    assert big.with_style("detail").metrics == ("cpu", "ram")
    small = W("small", "detail", "cpu")
    assert small.with_size("medium").metrics == ("cpu",)                         # growing keeps values


def test_toggle_respects_limit_and_minimum():
    cfg = W("small", "rings", "cpu", "ram")               # full: capacity 2
    assert cfg.toggled("disk") is None and not cfg.can_add("disk")
    assert cfg.toggled("ram").metrics == ("cpu",)
    assert W("small", "rings", "cpu").toggled("cpu") is None    # last value stays
    roomy = W("medium", "rings", "cpu")
    assert roomy.toggled("disk").metrics == ("cpu", "disk")
    assert roomy.toggled("nonexistent") is None


def test_sanitize_layout():
    assert sanitize_layout(None) == DEFAULT_LAYOUT
    assert sanitize_layout([]) == DEFAULT_LAYOUT
    assert len(sanitize_layout([{"size": "medium"}] * 50)) == MAX_WIDGETS
    assert sanitize_layout([{"style": "bars", "metrics": ["ram"]}])[0].style == "bars"


def test_roundtrip_through_json():
    raw = json.loads(json.dumps(layout_to_raw(DEFAULT_LAYOUT)))
    assert sanitize_layout(raw) == DEFAULT_LAYOUT


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_presets_are_valid(name):
    layout = PRESETS[name]
    assert 1 <= len(layout) <= MAX_WIDGETS
    for cfg in layout:
        assert 1 <= len(cfg.metrics) <= cfg.capacity
        assert len(set(cfg.metrics)) == len(cfg.metrics)
        assert all(m in METRICS for m in cfg.metrics)
    assert sanitize_layout(layout_to_raw(layout)) == layout      # survives sanitising unchanged


def test_store_persists_and_notifies():
    mem = _Mem()
    store = LayoutStore(mem)
    seen = []
    store.subscribe(seen.append)
    assert store.update(0, W("small", "bars", "cpu", "ram", "disk"))
    assert mem.saves == 1 and len(seen) == 1
    assert store.layout[0].style == "bars"
    assert not store.update(0, store.layout[0])                  # no change -> no save
    assert not store.update(99, W("small", "detail", "cpu"))
    assert not store.update(0, None)
    assert mem.saves == 1


def test_store_move_remove_add_reset():
    store = LayoutStore(_Mem())
    first, second = store.layout[0], store.layout[1]
    assert store.move(0, 1) and store.layout[:2] == [second, first]
    assert not store.move(0, -1)
    n = len(store.layout)
    assert store.remove(0) and len(store.layout) == n - 1
    assert store.add("medium", "numbers")
    added = store.layout[-1]
    assert (added.size, added.style) == ("medium", "numbers") and len(added.metrics) == 6
    store.reset()
    assert store.layout == DEFAULT_LAYOUT


def test_store_never_removes_last_widget_or_exceeds_max():
    store = LayoutStore(_Mem([{"size": "small", "style": "detail", "metrics": ["cpu"]}]))
    assert not store.remove(0)
    for _ in range(MAX_WIDGETS + 3):
        store.add("small", "rings")
    assert len(store.layout) == MAX_WIDGETS
    assert not store.add("small", "rings")


def test_store_apply_preset():
    store = LayoutStore(_Mem())
    assert store.apply_preset("numbers") and store.layout == PRESETS["numbers"]
    assert not store.apply_preset("does-not-exist")


def test_layout_persists_in_settings_file():
    settings = Settings()
    store = LayoutStore(settings)
    store.update(0, W("medium", "numbers", "cpu", "ram", "temp"))
    reloaded = LayoutStore(Settings.load())
    assert reloaded.layout[0] == W("medium", "numbers", "cpu", "ram", "temp")


def test_old_settings_file_without_widgets_gets_default_layout(tmp_path):
    from iox_stats.settings import config_dir

    path = config_dir() / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"theme": "dark", "tray_metrics": ["cpu"]}))     # a v0.2.0 file
    loaded = Settings.load()
    assert loaded.theme == "dark"
    assert LayoutStore(loaded).layout == DEFAULT_LAYOUT


def test_corrupt_widgets_entry_in_settings_is_repaired():
    from iox_stats.settings import config_dir

    path = config_dir() / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"widgets": "kaputt"}))
    assert LayoutStore(Settings.load()).layout == DEFAULT_LAYOUT
