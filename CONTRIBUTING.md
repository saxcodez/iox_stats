# Contributing to IOX Stats

Thanks for helping! IOX Stats is a non-commercial community project by saxcodez: bug reports, test results on
your Mac, ideas, requests and code are all welcome.

## Report a bug

Open an issue with the **Bug report** template and include:

- macOS version and Mac (Apple Silicon or Intel)
- what you did, what you expected, what happened
- the log file: menu bar item > **Open Log Folder** > `iox_stats.log` (or `python -m iox_stats --show-log`)
- for the widget gallery widget: `macos-widgets/widget-install.log` from `bash scripts/install_widgets.sh`

## Suggest a feature

Open an issue with the **Feature request** template. Check the roadmap in the README first - maybe it is planned
and you want to pick it up.

## Send code

1. Fork the repository and create a branch: `git checkout -b feature/my-idea`
2. Set up: `bash scripts/setup_macos.sh`, then `pip install pytest`
3. Make your change. Keep the Apple look (system fonts, system colours, glass surfaces) and keep it opt-in when it
   changes system behaviour (autostart, installing tools).
4. Add or update tests and run them: `QT_QPA_PLATFORM=offscreen python -m pytest`
5. Add a line under `## [Unreleased]` in `CHANGELOG.md`.
6. Open a pull request against `main` and describe what you tested on which Mac.

Swift changes in `macos-widgets/`: run `bash scripts/build_widgets.sh` (compile check) and
`bash scripts/install_widgets.sh` (install and show in the widget gallery) before opening the pull request.

## Code style

- Python 3.9+, type hints, small functions, no new dependencies without a good reason
- English for code, comments, UI text and docs
- No telemetry, no network access except the ping check

## Contribution terms

IOX Stats is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE); copyright stays with saxcodez.
By opening a pull request you confirm that the contribution is your own work and you grant saxcodez a perpetual,
worldwide, royalty-free right to use, modify and distribute it as part of IOX Stats under the project's license
or any future license of the project. You will be credited in the changelog.
