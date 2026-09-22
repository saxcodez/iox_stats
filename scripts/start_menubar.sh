#!/usr/bin/env bash
# Start the IOX Stats menu bar app now AND at every login - so the menu bar readout, its settings and the
# CPU temperature for the widget are always there. Run from the project folder:   bash scripts/start_menubar.sh
# Undo:  .venv/bin/python -m iox_stats --disable-login
set -uo pipefail
cd "$(dirname "$0")/.."
PY=".venv/bin/python"
AGENT="$HOME/Library/LaunchAgents/com.iox-stats.app.plist"

if [[ ! -x "$PY" ]]; then
  echo "No .venv yet - running the setup first."
  bash scripts/setup_macos.sh || exit 1
fi

"$PY" -m iox_stats --enable-login || { echo "PROBLEM: could not turn on Launch at Login"; exit 1; }

if pgrep -f "iox_stats( |$)" >/dev/null 2>&1 && ! launchctl print "gui/$(id -u)/com.iox-stats.app" >/dev/null 2>&1; then
  echo "IOX Stats is already running (started from a terminal). Quit it via its menu (Quit IOX Stats) and run this"
  echo "script again, so that macOS manages it from now on."
  exit 0
fi

launchctl bootout "gui/$(id -u)" "$AGENT" >/dev/null 2>&1
if launchctl bootstrap "gui/$(id -u)" "$AGENT"; then
  echo "IOX Stats runs in the menu bar now and starts at every login."
  echo "Click its menu bar item for the values, 2 / 1 value display, CPU temperature setup and more."
else
  echo "PROBLEM: macOS did not start it. Start it by hand:  $PY -m iox_stats"
  exit 1
fi
