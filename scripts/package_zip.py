#!/usr/bin/env python3
"""Build dist/IOX_Stats_vX.Y.Z.zip (top-level folder IOX_Stats_vX.Y.Z/) from the project tree."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_version import ROOT, package_version  # noqa: E402

EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", "dist", "build", ".venv", "venv"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".spec"}


def build(out_dir: Path | None = None) -> Path:
    ver = package_version()
    name = f"IOX_Stats_v{ver}"
    out_dir = out_dir or ROOT / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{name}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(ROOT.rglob("*")):
            rel = path.relative_to(ROOT)
            if path.is_dir() or set(rel.parts) & EXCLUDE_DIRS or path.suffix in EXCLUDE_SUFFIX:
                continue
            z.write(path, f"{name}/{rel.as_posix()}")
    return target


if __name__ == "__main__":
    print(build())
