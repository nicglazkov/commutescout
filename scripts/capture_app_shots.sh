#!/usr/bin/env bash
# Capture the phone-app screenshots the site shows (site/public/shots/app/)
# and, with --install, put them on the site in one step.
#
# Nothing personal can end up in them: the apps run in the iOS simulator
# and the Android emulator with a simulated location (downtown San
# Francisco for the map, the app's own scripted drive for navigation),
# fresh preferences, and a demo status bar (full battery, full signal, the
# clock set to the real minute so the arrival times agree with it).
#
# Needs: a Mac reachable over ssh with Xcode and the app's checkout at
# ~/src/commutescout-app (scripts/sync_mac.sh in the app repo copies it;
# scripts/ios_build.sh sim has been run once), and a booted Android
# emulator with the current debug APK installed. The emulator can run on
# this machine (ADB=adb, the default) or on the Mac (ADB_SSH=1 runs adb
# there over the same ssh connection).
#
# When the app changes, refresh the site's screenshots:
#
#   MAC=nic@mac-host IOS_UDID=<simulator udid> scripts/capture_app_shots.sh --install out/
#
# --install converts every capture to a 640 px wide WEBP, copies the five
# the site uses into site/public/shots/app/ (ios-map, ios-nav, ios-alert,
# android-map, android-nav) and rewrites site/public/shots/app/shots.json
# with the app version (the checkout's VERSION file) and today's date.
# The /app page prints that version and date under the screenshots, so a
# stale set is visible on the page. Look at each image before committing.
#
#   scripts/capture_app_shots.sh --check
#
# compares shots.json with the newest app release on GitHub (needs gh)
# and exits 1 when the screenshots are from an older version.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE_SHOTS="$ROOT/site/public/shots/app"
MANIFEST="$SITE_SHOTS/shots.json"

if [ "${1:-}" = "--check" ]; then
  have=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("app_version") or "unknown")' "$MANIFEST")
  latest=$(gh api repos/nicglazkov/commutescout-app/releases/latest --jq .tag_name)
  echo "screenshots: $have   latest app release: $latest"
  [ "v${have#v}" = "$latest" ] || { echo "the screenshots are older than the app: run with --install"; exit 1; }
  exit 0
fi

INSTALL=0
if [ "${1:-}" = "--install" ]; then INSTALL=1; shift; fi
OUT="${1:?output dir}"
MAC="${MAC:?ssh target for the Mac}"
IOS_UDID="${IOS_UDID:?simulator udid}"
BUNDLE=com.commutescout.drive
mkdir -p "$OUT"
# adb here, or on the Mac when the emulator runs there.
if [ "${ADB_SSH:-0}" = "1" ]; then
  ADB_BIN="${ADB:-\$HOME/Library/Android/sdk/platform-tools/adb}"
  adb() { ssh "$MAC" "$ADB_BIN $(printf '%q ' "$@")"; }
else
  ADB_BIN="${ADB:-adb}"
  adb() { "$ADB_BIN" "$@"; }
fi
APP_VERSION=$(ssh "$MAC" 'cat ~/src/commutescout-app/VERSION' | tr -d '[:space:]')

ssh "$MAC" "U=$IOS_UDID; B=$BUNDLE; S=\$(mktemp -d)
clock(){ xcrun simctl status_bar \$U override --time \"\$(date +%-I:%M)\" --batteryState charged --batteryLevel 100 --cellularBars 4 --wifiBars 3; }
xcrun simctl terminate \$U \$B 2>/dev/null || true
# The map around a simulated position, after the tiles have loaded.
xcrun simctl location \$U set $MAP_LAT,$MAP_LON
xcrun simctl launch \$U \$B -csResetPlaces -csResetPrefs >/dev/null
sleep 35; clock; sleep 2; xcrun simctl io \$U screenshot \$S/final-ios-map.png >/dev/null
xcrun simctl terminate \$U \$B; sleep 1
# A drive in progress: the route starts, then the simulator drives it.
xcrun simctl launch \$U \$B -csNavigateTo '$NAV_DEST' >/dev/null
sleep 20; xcrun simctl location \$U start --speed=16 --distance=40 $NAV_PATH
sleep 45; clock; sleep 2; xcrun simctl io \$U screenshot \$S/final-ios-nav.png >/dev/null
xcrun simctl location \$U clear; xcrun simctl terminate \$U \$B; sleep 1
# The app's own scripted drive, which passes a closure it warns about.
xcrun simctl location \$U set 37.3382,-121.8863
xcrun simctl launch \$U \$B -csAutoDrive >/dev/null
sleep 80; clock; sleep 2; xcrun simctl io \$U screenshot \$S/final-ios-alert.png >/dev/null
xcrun simctl terminate \$U \$B
echo \$S"
MAC_DIR=$(ssh "$MAC" 'ls -dt /var/folders/*/*/T/tmp.* /tmp/tmp.* 2>/dev/null | head -1')
scp -q "$MAC:$MAC_DIR/final-ios-*.png" "$OUT/"

# Android: demo status bar, then the same two states.
demo() { adb shell am broadcast -a com.android.systemui.demo -e command "$@" >/dev/null; }
adb shell settings put global sysui_demo_allowed 1
demo enter
demo battery -e level 100 -e plugged false
demo network -e wifi show -e level 4 -e fully true
demo network -e mobile show -e level 4 -e datatype none -e fully true
demo notifications -e visible false
aclock() { demo clock -e hhmm "$(date +%H%M)"; }
adb emu geo fix "$MAP_LON" "$MAP_LAT"
adb shell am force-stop $BUNDLE
adb shell am start -n $BUNDLE/.MainActivity --ez csResetPlaces true --ez csResetPrefs true >/dev/null
sleep 18; adb emu geo fix "$MAP_LON" "$MAP_LAT"; sleep 4; aclock; sleep 2
adb exec-out screencap -p > "$OUT/final-android-map.png"
adb shell am force-stop $BUNDLE; sleep 1
adb shell am start -n $BUNDLE/.MainActivity --ez csAutoDrive true >/dev/null
sleep 45; aclock; sleep 2
adb exec-out screencap -p > "$OUT/final-android-nav.png"
demo exit

python3 - "$OUT" <<'PY'
import glob, os, sys
from PIL import Image
for f in glob.glob(os.path.join(sys.argv[1], "final-*.png")):
    im = Image.open(f).convert("RGB")
    im.thumbnail((640, 640 * 3))
    im.save(f[:-4] + ".webp", "WEBP", quality=84, method=6)
PY

if [ "$INSTALL" = "1" ]; then
  for n in ios-map ios-nav ios-alert android-map android-nav; do
    cp "$OUT/final-$n.webp" "$SITE_SHOTS/$n.webp"
  done
  python3 - "$MANIFEST" "$APP_VERSION" <<'PY'
import datetime, json, sys
json.dump({"app_version": sys.argv[2], "captured": datetime.date.today().isoformat()},
          open(sys.argv[1], "w"), indent=2)
open(sys.argv[1], "a").write("\n")
PY
  echo "installed into $SITE_SHOTS (app $APP_VERSION); review them, then commit"
fi
ls -la "$OUT"
