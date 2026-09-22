"""Every release must have a matching changelog entry and release notes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_version  # noqa: E402


def test_version_changelog_and_release_notes_agree():
    assert check_version.check() == []


def test_tag_mismatch_is_detected():
    assert check_version.check("v9.9.9")


def test_zip_contains_versioned_top_folder(tmp_path):
    import zipfile

    import package_zip

    target = package_zip.build(tmp_path)
    ver = check_version.package_version()
    assert target.name == f"IOX_Stats_v{ver}.zip"
    with zipfile.ZipFile(target) as z:
        names = z.namelist()
    assert all(n.startswith(f"IOX_Stats_v{ver}/") for n in names)
    assert f"IOX_Stats_v{ver}/CHANGELOG.md" in names
    assert not any("__pycache__" in n or ".git/" in n for n in names)
