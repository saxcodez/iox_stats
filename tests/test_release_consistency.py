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


def test_community_files_and_macos_only_workflows():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    lic = (root / "LICENSE").read_text(encoding="utf-8")
    assert lic.startswith("Required Notice: Copyright") and "saxcodez" in lic
    assert "PolyForm Noncommercial License 1.0.0" in lic
    for rel in ("CONTRIBUTING.md", ".github/ISSUE_TEMPLATE/bug_report.md", ".github/ISSUE_TEMPLATE/feature_request.md",
                "scripts/build_widgets.sh", "scripts/install_widgets.sh", "docs/PROJECT_STATUS.md"):
        assert (root / rel).is_file(), rel
    for wf in (".github/workflows/ci.yml", ".github/workflows/release.yml"):
        assert "windows" not in (root / wf).read_text(encoding="utf-8").lower(), wf
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "saxcodez/iox_stats" in readme and "windows" not in readme.lower()
    assert "not for sale" in readme.lower() and "PolyForm Noncommercial" in readme
    from iox_stats import __github_url__, __version__

    assert __github_url__ == "https://github.com/saxcodez/iox_stats"
    assert f"**Current version:** {__version__}" in (root / "docs/PROJECT_STATUS.md").read_text(encoding="utf-8")
    assert "OWNER/" not in (root / "CHANGELOG.md").read_text(encoding="utf-8")
