# Release process

IOX Stats uses [Semantic Versioning](https://semver.org): `MAJOR.MINOR.PATCH`.

- **PATCH** (0.7.1): bug fixes only
- **MINOR** (0.8.0): new features, backwards compatible
- **MAJOR** (1.0.0): incompatible changes. Until 1.0.0 the project is in development and releases are marked as
  pre-releases.

## Checklist

1. Collect changes under `## [Unreleased]` in `CHANGELOG.md` (Added / Changed / Fixed / Removed).
2. Set the new version:
   - `iox_stats/__init__.py`: `__version__ = "X.Y.Z"`
   - `macos-widgets/project.yml`: `MARKETING_VERSION: "X.Y.Z"`
   - `CHANGELOG.md`: move `[Unreleased]` into `## [X.Y.Z] - YYYY-MM-DD`, update the compare links at the bottom
   - `docs/release-notes/vX.Y.Z.md`: highlights, install / upgrade notes, known limitations
   - `docs/PROJECT_STATUS.md`: current version and the verified-on-hardware table
3. Check:
   ```bash
   python scripts/check_version.py
   QT_QPA_PLATFORM=offscreen python -m pytest
   bash scripts/build_widgets.sh
   bash scripts/install_widgets.sh
   ```
4. Commit and tag:
   ```bash
   git commit -am "Release vX.Y.Z"
   git tag -a vX.Y.Z -m "IOX Stats vX.Y.Z"
   git push origin main --follow-tags
   ```
5. The `Release` workflow checks that the tag matches the version, runs the tests, builds the source package `IOX_Stats_vX.Y.Z.zip` and
   creates the GitHub Release with the text from `docs/release-notes/vX.Y.Z.md`.
6. Source ZIP with the version in its name: `python scripts/package_zip.py` -> `dist/IOX_Stats_vX.Y.Z.zip`.
