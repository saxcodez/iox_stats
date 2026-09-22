#!/usr/bin/env bash
# Build the widget gallery widget SIGNED, install "IOX Stats.app" to /Applications and register the widget.
# macOS only lists widgets of signed apps it has registered - the unsigned test build (build_widgets.sh) is not enough.
#
# Usage (from the project folder):   bash scripts/install_widgets.sh            (finds your Team ID itself)
#                                     bash scripts/install_widgets.sh ABCDE12345 (your Team ID)
set -uo pipefail
cd "$(dirname "$0")/../macos-widgets"
LOG="$(pwd)/widget-install.log"
: > "$LOG"
say() { echo "$*" | tee -a "$LOG"; }
APP_NAME="IOX Stats.app"
DEST="/Applications/$APP_NAME"

say "== IOX Stats widget install =="
say "macOS: $(sw_vers -productVersion 2>/dev/null)  CPU: $(uname -m)  Xcode: $(xcodebuild -version 2>/dev/null | head -1)"

# 1. Team ID: argument, env var, or the "Apple Development" certificate Xcode created for your Apple ID
TEAM="${1:-${IOX_TEAM_ID:-}}"
if [[ -z "$TEAM" ]]; then
  TEAM="$(security find-certificate -a -c "Apple Development" -p 2>/dev/null \
          | openssl x509 -noout -subject 2>/dev/null \
          | sed -n 's/.*OU *= *\([A-Z0-9]\{10\}\).*/\1/p' | head -1)"
fi
if [[ -n "$TEAM" ]]; then
  say "Signing team: $TEAM"
  SIGN=(DEVELOPMENT_TEAM="$TEAM" CODE_SIGN_STYLE=Automatic -allowProvisioningUpdates)
else
  say "No Apple Development certificate found - signing ad-hoc (local only)."
  say "If the widget does not show up afterwards: Xcode > Settings > Accounts > + > add your Apple ID,"
  say "then open IOXStats.xcodeproj, choose your Team for both targets, press Run once, and run this script again."
  SIGN=(CODE_SIGN_IDENTITY="-" CODE_SIGN_STYLE=Manual DEVELOPMENT_TEAM="" PROVISIONING_PROFILE_SPECIFIER="")
fi

# 2. Build
command -v xcodegen >/dev/null 2>&1 || { say "PROBLEM: XcodeGen missing. Run:  brew install xcodegen"; exit 1; }
say "-- generating the Xcode project"
xcodegen generate >>"$LOG" 2>&1 || { say "PROBLEM: xcodegen failed, see $LOG"; exit 1; }
say "-- building (Release, signed) - 1-3 minutes"
if ! xcodebuild -project IOXStats.xcodeproj -scheme IOXStats -configuration Release -destination 'platform=macOS' \
     -derivedDataPath build "${SIGN[@]}" build >>"$LOG" 2>&1; then
  say "RESULT: BUILD FAILED. The errors:"
  grep -E "error:|fatal error" "$LOG" | sed 's#^.*/macos-widgets/##' | sort -u | head -30 | tee -a "$LOG"
  exit 1
fi
BUILT="build/Build/Products/Release/$APP_NAME"
[[ -d "$BUILT" ]] || { say "PROBLEM: $BUILT not found after the build"; exit 1; }
codesign -dv "$BUILT" >>"$LOG" 2>&1
codesign -dv "$BUILT/Contents/PlugIns/IOXStatsWidgets.appex" >>"$LOG" 2>&1 \
  || { say "PROBLEM: the widget extension is missing inside the app"; exit 1; }

# 3. Install to /Applications (replaces an older copy)
say "-- installing to $DEST"
pkill -x "IOX Stats" 2>/dev/null; sleep 1
rm -rf "$DEST" 2>/dev/null || { say "PROBLEM: cannot replace $DEST (quit the app and try again)"; exit 1; }
ditto "$BUILT" "$DEST" || { say "PROBLEM: copy to /Applications failed"; exit 1; }

# 4. Register the widget and refresh the widget gallery
say "-- registering the widget"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$DEST" >>"$LOG" 2>&1
pluginkit -a "$DEST/Contents/PlugIns/IOXStatsWidgets.appex" >>"$LOG" 2>&1
open "$DEST"
sleep 3
killall chronod 2>/dev/null        # the widget daemon restarts by itself and re-reads the installed widgets
sleep 2

if pluginkit -m -p com.apple.widgetkit-extension 2>/dev/null | grep -qi "IOXStats"; then
  say "RESULT: WIDGET REGISTERED."
  say "Now: right-click the desktop > Edit Widgets > search \"IOX Stats\" > drag it onto the desktop."
  say "Keep the Python app running (python -m iox_stats) for live values incl. temperature."
else
  say "RESULT: the app is installed, but macOS has not listed the widget yet."
  say "Try: log out and in again (or restart), then look in Edit Widgets. Still missing? Send $LOG."
  pluginkit -m -v -p com.apple.widgetkit-extension >>"$LOG" 2>&1
fi
