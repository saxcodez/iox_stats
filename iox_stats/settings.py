"""Persistent user settings (JSON in the platform's config directory)."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List

from .layout import DEFAULT_LAYOUT, layout_to_raw, sanitize_layout
from .metrics import DEFAULT_TRAY, METRICS

THEMES = ("system", "light", "dark")
TRAY_STYLES = ("auto", "text", "compact")
MAX_TRAY_METRICS = 6
# menu bar display: how many values are visible at once. More selected values rotate through (in pairs / singly).
TRAY_MODES = {"two": 2, "one": 1}


def config_dir() -> Path:
    override = os.environ.get("IOX_STATS_CONFIG_DIR")
    if override:
        return Path(override)
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "IOXStats"


@dataclass
class Settings:
    theme: str = "system"
    interval_ms: int = 1000
    tray_metrics: List[str] = field(default_factory=lambda: list(DEFAULT_TRAY))
    ping_host: str = "1.1.1.1"
    ping_port: int = 443
    tray_style: str = "auto"   # auto = text on macOS/Linux, compact icon on Windows
    widgets: list = field(default_factory=lambda: layout_to_raw(DEFAULT_LAYOUT))   # see layout.py
    always_on_top: bool = False
    glass: bool = True          # native blur behind the window where the OS supports it
    first_run_done: bool = False  # the one-time "launch at login?" question has been asked
    helper_prompt_done: bool = False  # the one-time "set up CPU temperature?" question has been asked (macOS)
    share_with_widgets: bool = True   # macOS: write snapshot.json for the widget gallery widget
    desktop_mode: bool = False        # widgets sit on the desktop (frameless, behind other windows)
    window_pos: list = field(default_factory=list)   # [x, y] of the window / desktop widgets, empty = default
    tray_mode: str = "two"     # "two" = two values side by side, "one" = a single value (see TRAY_MODES)
    start_hidden: bool = False  # start with no window, menu bar only (independent of autostart)

    def sanitize(self) -> "Settings":
        if self.theme not in THEMES:
            self.theme = "system"
        if self.tray_style not in TRAY_STYLES:
            self.tray_style = "auto"
        if self.tray_mode not in TRAY_MODES:
            self.tray_mode = "two"
        self.interval_ms = int(min(10000, max(500, self.interval_ms)))
        self.tray_metrics = [m for m in self.tray_metrics if m in METRICS][:MAX_TRAY_METRICS] or list(DEFAULT_TRAY)
        self.ping_port = int(min(65535, max(1, self.ping_port)))
        self.widgets = layout_to_raw(sanitize_layout(self.widgets))
        pos = self.window_pos
        if not (isinstance(pos, (list, tuple)) and len(pos) == 2 and all(isinstance(v, (int, float)) for v in pos)):
            pos = []
        self.window_pos = [int(v) for v in pos]
        return self

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or config_dir() / "settings.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
            return cls(**known).sanitize()
        except (OSError, ValueError, TypeError):
            return cls().sanitize()

    def save(self, path: Path | None = None) -> None:
        path = path or config_dir() / "settings.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(self.sanitize()), indent=2), encoding="utf-8")
        except OSError:
            pass
