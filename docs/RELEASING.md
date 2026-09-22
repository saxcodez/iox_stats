# Release-Prozess

Wir nutzen [Semantic Versioning](https://semver.org): `MAJOR.MINOR.PATCH`

- **PATCH** (0.1.1): nur Bugfixes
- **MINOR** (0.2.0): neue Features, abwärtskompatibel
- **MAJOR** (1.0.0): inkompatible Änderungen (bis 1.0.0 gilt das Projekt als "in Entwicklung")

## Checkliste für jede Version

1. Änderungen unter `## [Unreleased]` in `CHANGELOG.md` sammeln (Added / Changed / Fixed / Removed).
2. Neue Version festlegen und eintragen:
   - `iox_stats/__init__.py` -> `__version__ = "X.Y.Z"`
   - `CHANGELOG.md`: `## [Unreleased]` Inhalt in `## [X.Y.Z] - JJJJ-MM-TT` verschieben, Vergleichslinks unten anpassen
   - `docs/release-notes/vX.Y.Z.md` anlegen (Vorlage: vorherige Datei - Highlights, Install, Known limitations, Upgrade notes)
3. Prüfen:
   ```bash
   python scripts/check_version.py        # Version, Changelog und Release Notes passen zusammen?
   QT_QPA_PLATFORM=offscreen python -m pytest
   ```
4. Committen und Tag setzen:
   ```bash
   git commit -am "Release vX.Y.Z"
   git tag -a vX.Y.Z -m "IOX Stats vX.Y.Z"
   git push origin main --follow-tags
   ```
5. Der Workflow `Release` (`.github/workflows/release.yml`) prüft Tag = Version, führt die Tests aus,
   baut macOS-/Windows-/Linux-Apps und legt das GitHub Release mit den Release Notes aus
   `docs/release-notes/vX.Y.Z.md` an (Versionen `0.x` werden als Pre-release markiert).
6. Optional: Quell-ZIP mit Versionsnummer erzeugen: `python scripts/package_zip.py` -> `dist/IOX_Stats_vX.Y.Z.zip`.

Ordnername beim Ablegen von Kopien: `IOX_Stats_vX.Y.Z`.
