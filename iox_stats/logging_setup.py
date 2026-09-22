"""File logging for diagnostics: a small rotating log in the config folder, plus uncaught-exception capture.

Location: ``<config dir>/logs/iox_stats.log`` (macOS: ``~/Library/Application Support/IOXStats/logs``).
Kept small on purpose (5 files x 1 MB) - this is for "what went wrong", not full telemetry, and nothing
here is sent anywhere.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from . import __app_name__, __version__
from .settings import config_dir

LOG_NAME = "iox_stats.log"
_configured = False


def log_dir() -> Path:
    return config_dir() / "logs"


def log_path() -> Path:
    return log_dir() / LOG_NAME


def setup(level: int = logging.INFO) -> logging.Logger:
    """Configure the ``iox_stats`` logger once; safe to call more than once."""
    global _configured
    logger = logging.getLogger("iox_stats")
    if _configured:
        return logger
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    try:
        log_dir().mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.handlers.RotatingFileHandler(
            log_path(), maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    except OSError:
        pass  # e.g. read-only config dir: still log to stderr below
    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(fmt)
    logger.addHandler(stream)
    logger.propagate = False
    _configured = True
    logger.info("%s %s starting (%s)", __app_name__, __version__, sys.platform)
    _install_excepthook(logger)
    return logger


def _install_excepthook(logger: logging.Logger) -> None:
    previous = sys.excepthook

    def hook(exc_type, exc, tb):
        if exc_type is KeyboardInterrupt:
            previous(exc_type, exc, tb)
            return
        logger.critical("Unhandled exception", exc_info=(exc_type, exc, tb))
        previous(exc_type, exc, tb)

    sys.excepthook = hook


def tail(n: int = 200) -> Optional[str]:
    """Last ``n`` lines of the current log file, or None if it does not exist."""
    p = log_path()
    if not p.is_file():
        return None
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    return "\n".join(lines[-n:])
