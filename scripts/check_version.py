#!/usr/bin/env python3
"""Verify that version, CHANGELOG and release notes agree.

Usage:  python scripts/check_version.py [vX.Y.Z]     (tag argument optional, e.g. in the release workflow)
Exit code 0 = consistent, 1 = problem (messages on stderr).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")


def package_version() -> str:
    text = (ROOT / "iox_stats" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        raise SystemExit("could not find __version__ in iox_stats/__init__.py")
    return m.group(1)


def changelog_versions() -> list:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return re.findall(r"^## \[(\d+\.\d+\.\d+[^\]]*)\]", text, re.M)


def check(tag: str | None = None) -> list:
    problems = []
    ver = package_version()
    if not SEMVER.match(ver):
        problems.append(f"version {ver!r} is not valid Semantic Versioning")
    versions = changelog_versions()
    if not versions:
        problems.append("CHANGELOG.md has no released version section")
    elif versions[0] != ver:
        problems.append(f"newest CHANGELOG entry is {versions[0]} but __version__ is {ver}")
    if not (ROOT / "docs" / "release-notes" / f"v{ver}.md").exists():
        problems.append(f"missing docs/release-notes/v{ver}.md")
    spec = ROOT / "macos-widgets" / "project.yml"
    if spec.exists():
        m = re.search(r'MARKETING_VERSION:\s*"([^"]+)"', spec.read_text(encoding="utf-8"))
        if not m or m.group(1) != ver:
            problems.append(f"macos-widgets/project.yml MARKETING_VERSION is {m.group(1) if m else 'missing'}, expected {ver}")
    if tag and tag != f"v{ver}":
        problems.append(f"tag {tag} does not match version v{ver}")
    return problems


if __name__ == "__main__":
    issues = check(sys.argv[1] if len(sys.argv) > 1 else None)
    for i in issues:
        print(f"ERROR: {i}", file=sys.stderr)
    if not issues:
        print(f"OK: version {package_version()} is consistent")
    raise SystemExit(1 if issues else 0)
