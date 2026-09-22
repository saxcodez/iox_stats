#!/usr/bin/env bash
# Build the widget gallery widget SIGNED with your Apple ID team, install "IOX Stats.app" to /Applications,
# remove stale test-build copies and register the widget.
# macOS lists widgets only from apps signed with a development team - an unsigned or ad-hoc build is not enough.
#
# Usage (from the project folder):   bash scripts/install_widgets.sh             finds your Team ID itself
#                                     bash scripts/install_widgets.sh ABCDE12345  use this Team ID
#                                     bash scripts/install_widgets.sh --adhoc     no team (widget usually NOT listed)
set -uo pipefail
cd "$(dirname "$0")/../macos-widgets"
LOG="$(pwd)/widget-install.log"
: > "$LOG"
say() { echo "$*" | tee -a "$LOG"; }
APP_NAME="IOX Stats.app"
DEST="/Applications/$APP_NAME"
LSREG=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister

say "== IOX Stats widget install =="
say "macOS: $(sw_vers -productVersion 2>/dev/null)  CPU: $(uname -m)  $(xcodebuild -version 2>/dev/null | head -1)"

# 1. Team ID: argument, env var, Xcode's account list, or the "Apple Development" certificate
ADHOC=0
TEAM=""
case "${1:-}" in
  --adhoc) ADHOC=1 ;;
  "") TEAM="${IOX_TEAM_ID:-}" ;;
  *) TEAM="$1" ;;
esac
if [[ $ADHOC -eq 0 && -z "$TEAM" ]]; then
  TEAM="$( { defaults read com.apple.dt.Xcode IDEProvisioningTeamByIdentifier 2>/dev/null;
             defaults read com.apple.dt.Xcode IDEProvisioningTeams 2>/dev/null; } \
           | grep -o 'teamID = [A-Z0-9]\{10\}' | head -1 | awk '{print $3}')"
fi
if [[ $ADHOC -eq 0 && -z "$TEAM" ]]; then
  TEAM="$(security find-certificate -a -c "Apple Development" -p 2>/dev/null \
          | openssl x509 -noout -subject 2>/dev/null \
          | sed -n 's/.*OU *= *\([A-Z0-9]\{10\}\).*/\1/p' | head -1)"
fi
if [[ $ADHOC -eq 1 ]]; then
  say "Signing ad-hoc (--adhoc). macOS usually does NOT list widgets from ad-hoc signed apps."
  SIGN=(CODE_SIGN_IDENTITY="-" CODE_SIGN_STYLE=Manual DEVELOPMENT_TEAM="" PROVISIONING_PROFILE_SPECIFIER="")
elif [[ -n "$TEAM" ]]; then
  say "Signing team: $TEAM"
  SIGN=(DEVELOPMENT_TEAM="$TEAM" CODE_SIGN_STYLE=Automatic -allowProvisioningUpdates)
else
  say "PROBLEM: no Apple ID / signing team found in Xcode."
  say "macOS only lists widgets from apps signed with a development team (a free Apple ID is enough):"
  say "  1. Open Xcode > Settings (Cmd+,) > Accounts > + (bottom left) > Apple ID > sign in."
  say "  2. Run this script again:  bash scripts/install_widgets.sh"
  say "  (Your Team ID is shown there too - you can pass it: bash scripts/install_widgets.sh ABCDE12345)"
  exit 1
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
  grep -qi "No Account for Team\|No signing certificate\|requires a development team" "$LOG" && \
    say "Hint: sign in with your Apple ID in Xcode > Settings > Accounts, then run the script again."
  exit 1
fi
BUILT="build/Build/Products/Release/$APP_NAME"
APPEX_REL="Contents/PlugIns/IOXStatsWidgets.appex"
[[ -d "$BUILT/$APPEX_REL" ]] || { say "PROBLEM: the widget extension is missing inside the built app"; exit 1; }
WIDGET_ID="$(/usr/libexec/PlistBuddy -c 'Print CFBundleIdentifier' "$BUILT/$APPEX_REL/Contents/Info.plist" 2>/dev/null)"
say "Widget id: $WIDGET_ID"
say "Signature: $(codesign -dv "$BUILT/$APPEX_REL" 2>&1 | grep -E '^TeamIdentifier|^Signature' | tr '\n' ' ')"
if ! codesign -d --entitlements - "$BUILT/$APPEX_REL" 2>/dev/null | grep -q "com.apple.security.app-sandbox"; then
  say "PROBLEM: the signed widget has no App Sandbox entitlement - macOS would reject it (\"plug-ins must be sandboxed\")."
  say "Check the entitlements properties in macos-widgets/project.yml, then run this script again."
  exit 1
fi
say "Sandbox entitlement: OK"

# 3. Remove stale copies: old test builds carry the same id, and macOS may pick one of those unsigned copies
say "-- removing stale copies"
pkill -x "IOX Stats" 2>/dev/null; sleep 1
for dd in "$HOME"/Library/Developer/Xcode/DerivedData/IOXStats-*; do
  [[ -d "$dd" ]] || continue
  find "$dd" -maxdepth 6 -type d -name "$APP_NAME" 2>/dev/null | while read -r p; do "$LSREG" -u "$p" >/dev/null 2>&1; done
  rm -rf "$dd" && say "   removed $(basename "$dd")"
done
# build products of other project copies (older ZIP folders, a git checkout): unregister and delete them
mdfind "kMDItemCFBundleIdentifier == 'com.saxcodez.IOXStats*'" 2>/dev/null \
  | grep "/macos-widgets/build/Build/Products/" | grep -v "^$(pwd)/$BUILT" | while read -r p; do
    "$LSREG" -u "$p" >/dev/null 2>&1
    pluginkit -r "$p" >/dev/null 2>&1
    rm -rf "$p" && say "   removed old build copy: $p"
  done
if [[ -n "$WIDGET_ID" ]]; then
  pluginkit -m -v -i "$WIDGET_ID" 2>/dev/null | awk -F'\t' '{print $NF}' | while read -r p; do
    [[ -n "$p" && "$p" != "$DEST/$APPEX_REL" ]] && pluginkit -r "$p" >/dev/null 2>&1 && say "   unregistered $p"
  done
fi

# 4. Install to /Applications
say "-- installing to $DEST"
rm -rf "$DEST" 2>/dev/null || { say "PROBLEM: cannot replace $DEST (quit the app and try again)"; exit 1; }
ditto "$BUILT" "$DEST" || { say "PROBLEM: copy to /Applications failed"; exit 1; }
"$LSREG" -u "$BUILT" >/dev/null 2>&1
rm -rf "$BUILT"                     # only one copy with this id should exist on the Mac

# 5. Register and refresh the widget gallery
say "-- registering the widget"
"$LSREG" -f "$DEST" >>"$LOG" 2>&1
pluginkit -a "$DEST/$APPEX_REL" >>"$LOG" 2>&1
open "$DEST"
sleep 3
killall chronod 2>/dev/null         # the widget daemon restarts by itself and re-reads the installed widgets
sleep 3

if [[ -n "$WIDGET_ID" ]] && pluginkit -m -i "$WIDGET_ID" 2>/dev/null | grep -q "$WIDGET_ID"; then
  say "RESULT: WIDGET REGISTERED."
  say "Now: right-click the desktop > Edit Widgets > search \"IOX Stats\"."
  say "Not there? System Settings > Desktop & Dock > Widgets: turn on \"Show Widgets: On Desktop\", then log out and in."
else
  say "RESULT: the app is installed, but macOS has not listed the widget yet."
  say "Log out and in (or restart), then check Edit Widgets. Still missing? Run:  bash scripts/widget_doctor.sh"
fi
