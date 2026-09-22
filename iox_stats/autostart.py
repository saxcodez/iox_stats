"""Launch at login - opt-in and reversible on macOS, Windows and Linux.

* macOS:   LaunchAgent plist in ``~/Library/LaunchAgents``
* Windows: ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`` (per user, no admin rights)
* Linux:   ``~/.config/autostart/iox-stats.desktop``

Nothing is ever installed system-wide, and ``disable()`` removes exactly what ``enable()`` created.
The autostart command adds ``--background`` so the app starts quietly in the menu bar / tray.
"""

from __future__ import annotations

import os
import plistlib
import shlex
import sys
from pathlib import Path
from typing import List, Optional

APP_ID = "com.iox-stats.app"
APP_NAME = "IOX Stats"
WIN_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
BACKGROUND_FLAG = "--background"


def launch_command(frozen: Optional[bool] = None, executable: Optional[str] = None) -> List[str]:
    """Command line that starts IOX Stats quietly in the background."""
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    exe = executable or sys.executable
    base = [exe] if frozen else [exe, "-m", "iox_stats"]
    return base + [BACKGROUND_FLAG]


class Autostart:
    def __init__(self, platform: Optional[str] = None, home: Optional[Path] = None,
                 command: Optional[List[str]] = None):
        self.platform = platform or sys.platform
        self.home = Path(home) if home else Path.home()
        self.command = command or launch_command()

    # -- helpers -------------------------------------------------------------
    @property
    def supported(self) -> bool:
        return self.platform == "darwin" or self.platform.startswith(("win", "linux"))

    @property
    def path(self) -> Optional[Path]:
        """File that represents the login item (None on Windows: registry value)."""
        if self.platform == "darwin":
            return self.home / "Library" / "LaunchAgents" / f"{APP_ID}.plist"
        if self.platform.startswith("linux"):
            cfg = Path(os.environ.get("XDG_CONFIG_HOME", self.home / ".config"))
            return cfg / "autostart" / "iox-stats.desktop"
        return None

    # -- public API ----------------------------------------------------------
    def is_enabled(self) -> bool:
        if self.platform.startswith("win"):
            return self._win_get() is not None
        p = self.path
        return bool(p and p.exists())

    def enable(self) -> bool:
        try:
            if self.platform == "darwin":
                self._write(self.path, plistlib.dumps({
                    "Label": APP_ID,
                    "ProgramArguments": self.command,
                    "RunAtLoad": True,
                    "ProcessType": "Interactive",
                    "LimitLoadToSessionType": "Aqua",
                }))
            elif self.platform.startswith("linux"):
                exec_line = " ".join(shlex.quote(c) for c in self.command)
                text = ("[Desktop Entry]\nType=Application\n"
                        f"Name={APP_NAME}\nComment=System status widgets\n"
                        f"Exec={exec_line}\nTerminal=false\nX-GNOME-Autostart-enabled=true\n")
                self._write(self.path, text.encode("utf-8"))
            elif self.platform.startswith("win"):
                self._win_set(" ".join(f'"{c}"' if " " in c else c for c in self.command))
            else:
                return False
        except OSError:
            return False
        return self.is_enabled()

    def disable(self) -> bool:
        try:
            if self.platform.startswith("win"):
                self._win_delete()
            else:
                p = self.path
                if p and p.exists():
                    p.unlink()
        except OSError:
            return False
        return not self.is_enabled()

    def set_enabled(self, enabled: bool) -> bool:
        return self.enable() if enabled else self.disable()

    # -- backends ------------------------------------------------------------
    @staticmethod
    def _write(path: Optional[Path], data: bytes) -> None:
        assert path is not None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def _win_get(self) -> Optional[str]:
        import winreg  # type: ignore[import-not-found]

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY) as key:
                return winreg.QueryValueEx(key, APP_NAME)[0]
        except OSError:
            return None

    def _win_set(self, value: str) -> None:
        import winreg  # type: ignore[import-not-found]

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, value)

    def _win_delete(self) -> None:
        import winreg  # type: ignore[import-not-found]

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass
