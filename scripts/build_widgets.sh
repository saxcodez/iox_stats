#!/usr/bin/env bash
# Test-build the macOS widget gallery widget (macos-widgets/) and write a log you can send for troubleshooting.
# Run from the project folder:   bash scripts/build_widgets.sh
# Needs: Xcode (App Store) and XcodeGen (brew install xcodegen). No signing needed for this test build.
set -uo pipefail
cd "$(dirname "$0")/../macos-widgets"
LOG="$(pwd)/widget-build.log"
: > "$LOG"
say() { echo "$*" | tee -a "$LOG"; }

say "== IOX Stats widget test build =="
say "macOS: $(sw_vers -productVersion 2>/dev/null)  CPU: $(uname -m)"

DEV="$(xcode-select -p 2>/dev/null || true)"
if [[ "$DEV" != *Xcode*.app* ]]; then
  say "PROBLEM: the full Xcode app is not selected (currently: ${DEV:-none})."
  say "  1. Install Xcode from the App Store and open it once (accept the license)."
  say "  2. Run:  sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"
  exit 1
fi
say "Xcode: $(xcodebuild -version 2>/dev/null | tr '\n' ' ')"

if ! command -v xcodegen >/dev/null 2>&1; then
  say "PROBLEM: XcodeGen missing. Run:  brew install xcodegen"
  exit 1
fi
say "XcodeGen: $(xcodegen --version 2>/dev/null)"

say "-- generating IOXStats.xcodeproj"
xcodegen generate >>"$LOG" 2>&1 || { say "PROBLEM: xcodegen failed, see $LOG"; exit 1; }

say "-- building (unsigned, Debug) - this takes 1-3 minutes"
xcodebuild -project IOXStats.xcodeproj -scheme IOXStats -configuration Debug -destination 'platform=macOS' \
  CODE_SIGNING_ALLOWED=NO CODE_SIGN_IDENTITY="" build >>"$LOG" 2>&1
RC=$?

echo
if [[ $RC -eq 0 ]]; then
  say "RESULT: BUILD SUCCEEDED - the Swift code compiles."
  say "Next: open IOXStats.xcodeproj, set your Team for both targets, press Run (Cmd+R), then add the widget."
else
  say "RESULT: BUILD FAILED. The errors:"
  grep -E "error:|fatal error" "$LOG" | sed 's#^.*/macos-widgets/##' | sort -u | head -40 | tee -a "$LOG.errors"
  echo
  echo "Send the lines above (or the whole file $LOG)."
fi
exit $RC
