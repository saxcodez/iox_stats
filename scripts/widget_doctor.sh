#!/usr/bin/env bash
# Collects everything needed to find out why the IOX Stats widget does not show up in Edit Widgets.
# Run from the project folder:   bash scripts/widget_doctor.sh
# Writes macos-widgets/widget-doctor.txt (no personal files, only app/widget/system info). Send that file.
set -uo pipefail
cd "$(dirname "$0")/../macos-widgets"
OUT="$(pwd)/widget-doctor.txt"
APP="/Applications/IOX Stats.app"
APPEX="$APP/Contents/PlugIns/IOXStatsWidgets.appex"
LSREG=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
sec() { printf '\n===== %s =====\n' "$1"; }

{
  sec "system"
  sw_vers; uname -m; xcodebuild -version 2>&1 | head -2
  sec "installed app"
  ls -ld "$APP" "$APPEX" 2>&1
  WID="$(/usr/libexec/PlistBuddy -c 'Print CFBundleIdentifier' "$APPEX/Contents/Info.plist" 2>/dev/null)"
  echo "widget id: ${WID:-?}"
  sec "widget Info.plist (NSExtension, versions)"
  /usr/libexec/PlistBuddy -c 'Print' "$APPEX/Contents/Info.plist" 2>&1 \
    | grep -E "CFBundle(Identifier|ShortVersionString|Version|Executable|PackageType)|NSExtension|widgetkit|LSMinimum" 
  sec "signatures"
  codesign -dv "$APP" 2>&1 | grep -E "Identifier|TeamIdentifier|Signature|Authority"
  codesign -dv "$APPEX" 2>&1 | grep -E "Identifier|TeamIdentifier|Signature|Authority"
  codesign --verify --deep --strict "$APP" 2>&1 && echo "codesign verify: OK"
  sec "widget entitlements"
  codesign -d --entitlements - --xml "$APPEX" 2>/dev/null | plutil -p - 2>&1
  sec "pluginkit registrations"
  pluginkit -m -v -p com.apple.widgetkit-extension 2>&1 | grep -i iox || echo "(IOX not registered with pluginkit)"
  sec "all copies with this id (should be exactly one, in /Applications)"
  mdfind "kMDItemCFBundleIdentifier == 'com.saxcodez.IOXStats*'" 2>&1
  "$LSREG" -dump 2>/dev/null | grep -E "^path:.*IOX Stats\.app" | sort -u | head -20
  sec "desktop widget setting"
  defaults read com.apple.WindowManager StandardHideWidgets 2>&1
  defaults read com.apple.WindowManager StageManagerHideWidgets 2>&1
  sec "widget system log, last 20 minutes (IOX lines)"
  log show --last 20m --style compact \
    --predicate 'process == "chronod" OR process == "pkd" OR process == "WidgetKitExtensionHost" OR process == "NotificationCenter" OR process == "IOXStatsWidgets"' 2>/dev/null \
    | grep -i -E "ioxstats|IOX Stats" | tail -80
} > "$OUT" 2>&1

echo "Written: $OUT"
echo "Please send this file (or paste its content)."
