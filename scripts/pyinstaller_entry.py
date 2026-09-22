"""Entry point used by PyInstaller (a package __main__ with relative imports cannot be frozen directly)."""

from iox_stats.app import main

if __name__ == "__main__":
    raise SystemExit(main())
