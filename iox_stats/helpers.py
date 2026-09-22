"""Sensor helper tools for the CPU temperature on macOS.

macOS has no public, unprivileged temperature API and IOX Stats does not need (or install) any kernel
driver. The temperature comes from a small command line tool that reads Apple's sensors from user space:

* Apple Silicon (M1-M5): ``macmon``        (``brew install macmon``)
* Intel Macs:            ``osx-cpu-temp``  (``brew install osx-cpu-temp``)

This module finds those tools - also when the app was started at login, where ``PATH`` does not contain
Homebrew - and can install the right one through Homebrew after the user agreed. Nothing here needs an
administrator password.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

# Places where Homebrew / cargo put tools. A LaunchAgent or the Finder start apps with a minimal PATH.
SEARCH_DIRS: Tuple[str, ...] = (
    "/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin", "/usr/local/sbin",
    "~/.cargo/bin", "~/.local/bin", "/opt/local/bin",
)
BREW_URL = "https://brew.sh"
BREW_INSTALL_HINT = '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'


def find_tool(name: str, search_dirs: Sequence[str] = SEARCH_DIRS) -> Optional[str]:
    """Full path of ``name`` (PATH first, then the usual Homebrew locations) or None."""
    found = shutil.which(name)
    if found:
        return found
    for directory in search_dirs:
        candidate = os.path.join(os.path.expanduser(directory), name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def find_brew() -> Optional[str]:
    return find_tool("brew")


def recommended_tool(machine: Optional[str] = None) -> str:
    """``macmon`` on Apple Silicon, ``osx-cpu-temp`` on Intel Macs."""
    return "macmon" if (machine or platform.machine()).lower() in ("arm64", "aarch64") else "osx-cpu-temp"


@dataclass(frozen=True)
class HelperStatus:
    """What is installed and what could be done about it."""

    supported: bool                 # only macOS needs a helper
    tool: Optional[str]             # installed helper (name) or None
    path: Optional[str]
    recommended: str                # the tool that fits this Mac
    brew: Optional[str]             # path of Homebrew or None

    @property
    def ready(self) -> bool:
        return bool(self.tool) or not self.supported

    @property
    def can_install(self) -> bool:
        return self.supported and not self.tool and bool(self.brew)

    @property
    def needs_homebrew(self) -> bool:
        return self.supported and not self.tool and not self.brew

    def summary(self) -> str:
        if not self.supported:
            return "CPU temperature: built-in sensors"
        if self.tool:
            return f"CPU temperature: {self.tool} active"
        if self.brew:
            return f"CPU temperature: not set up (installs {self.recommended})"
        return "CPU temperature: Homebrew needed"


def status(platform_name: Optional[str] = None, machine: Optional[str] = None,
           finder: Callable[[str], Optional[str]] = find_tool) -> HelperStatus:
    supported = (platform_name or sys.platform) == "darwin"
    rec = recommended_tool(machine)
    tool = path = None
    if supported:
        # prefer the tool that fits the CPU, but accept the other one if it is the only one present
        for name in (rec, "macmon", "osx-cpu-temp"):
            p = finder(name)
            if p:
                tool, path = name, p
                break
    return HelperStatus(supported, tool, path, rec, finder("brew") if supported else None)


def install_command(st: HelperStatus) -> List[str]:
    """Command that installs the recommended helper (empty if that is not possible)."""
    if not st.can_install or not st.brew:
        return []
    return [st.brew, "install", st.recommended]


def install_environment() -> dict:
    env = dict(os.environ)
    env.setdefault("HOMEBREW_NO_ANALYTICS", "1")
    env["HOMEBREW_NO_AUTO_UPDATE"] = "1"         # install only, do not update the whole Homebrew first
    env["HOMEBREW_NO_INSTALL_CLEANUP"] = "1"
    env["PATH"] = os.pathsep.join([*(os.path.expanduser(d) for d in SEARCH_DIRS), env.get("PATH", "")])
    return env


def run_install(st: HelperStatus, runner: Callable = subprocess.run, timeout: int = 900) -> Tuple[bool, str]:
    """Install the helper (blocking). Returns ``(ok, message)``."""
    cmd = install_command(st)
    if not cmd:
        if st.needs_homebrew:
            return False, f"Homebrew is not installed. Get it from {BREW_URL}, then try again."
        return False, "Nothing to install."
    try:
        result = runner(cmd, capture_output=True, text=True, timeout=timeout, env=install_environment())
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Could not run Homebrew: {exc}"
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-3:]
        return False, "Installation failed: " + " ".join(tail)
    return True, f"{st.recommended} installed."


def install_async(st: HelperStatus, on_done: Callable[[bool, str], None], runner: Callable = subprocess.run) -> threading.Thread:
    """Install in a background thread; ``on_done(ok, message)`` is called from that thread."""

    def work() -> None:
        ok, msg = run_install(st, runner)
        on_done(ok, msg)

    thread = threading.Thread(target=work, name="iox-helper-install", daemon=True)
    thread.start()
    return thread
