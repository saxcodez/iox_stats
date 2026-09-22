#!/usr/bin/env bash
# One-shot setup for macOS: virtual environment, Python packages, CPU temperature helper.
# Run from the project folder:   bash scripts/setup_macos.sh
# Nothing here needs sudo. Every step can be skipped by answering "n".
set -euo pipefail
cd "$(dirname "$0")/.."

ask() { read -r -p "$1 [Y/n] " a; [[ -z "$a" || "$a" =~ ^[YyJj] ]]; }

echo "== IOX Stats setup =="
PY="$(command -v python3 || true)"
[[ -n "$PY" ]] || { echo "python3 not found. Install it from https://www.python.org/downloads/ or with: brew install python"; exit 1; }

if [[ ! -d .venv ]]; then
  echo "Creating .venv ..."
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt
if [[ "$(uname)" == "Darwin" ]]; then
  python -m pip install pyobjc-framework-Cocoa      # real menu bar text and blur behind the window
fi

if [[ "$(uname)" == "Darwin" ]]; then
  echo
  echo "The CPU temperature needs a small helper tool (no kernel driver, no admin password)."
  if ask "Install it now with Homebrew?"; then
    python -m iox_stats --install-helpers || echo "Skipped: see the message above (Homebrew missing?)."
  fi
  if command -v xcodegen >/dev/null 2>&1; then
    echo
    echo "XcodeGen found. For the macOS widget gallery:  cd macos-widgets && xcodegen generate && open IOXStats.xcodeproj"
  else
    echo
    echo "For the macOS widget gallery install XcodeGen (brew install xcodegen), see macos-widgets/README.md."
  fi
fi

echo
echo "Done. Start with:"
echo "  source .venv/bin/activate && python -m iox_stats"
echo "Desktop widgets (live, behind your windows):  python -m iox_stats --desktop"
