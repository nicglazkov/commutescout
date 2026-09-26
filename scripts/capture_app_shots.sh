#!/usr/bin/env bash
# Capture the phone-app screenshots the site shows (site/public/shots/app/).
#
# Nothing personal can end up in them: the apps run in the iOS simulator
# and the Android emulator with a simulated location (downtown San
# Francisco for the map, the app's own scripted drive for navigation),
# fresh preferences, and a demo status bar (full battery, full signal, the
# clock set to the real minute so the arrival times agree with it).
#
# Needs: a Mac reachable over ssh with Xcode and the app's checkout at
# ~/src/commutescout-app (scripts/ios_build.sh sim has been run once), and
# a booted Android emulator with the debug APK installed locally.
#
#   MAC=nic@mac-host IOS_UDID=<simulator udid> scripts/capture_app_shots.sh out/
#
# Every PNG is also written as a 640 px wide WEBP beside it; copy the ones
# to use into site/public/shots/app/ (ios-map, ios-nav, ios-alert,
# android-map, android-nav). Look at each one first.
set -euo pipefail

OUT="${1:?output dir}"
MAC="${MAC:?ssh target for the Mac}"
IOS_UDID="${IOS_UDID:?simulator udid}"
ADB="${ADB:-adb}"
BUNDLE=com.commutescout.drive
mkdir -p "$OUT"

# Downtown San Francisco, the Ferry Building: a public landmark.
MAP_LAT=37.7955; MAP_LON=-122.3937
# A short public drive: Ferry Building toward the Golden Gate Bridge,
# with the simulator moving the phone along the Embarcadero.
NAV_DEST="37.8199,-122.4783,Golden Gate Bridge"
NAV_PATH="37.7955,-122.3937 37.8043,-122.4010 37.8058,-122.4110 37.8054,-122.4300 37.8060,-122.4400 37.8075,-122.4480"

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
demo() { "$ADB" shell am broadcast -a com.android.systemui.demo -e command "$@" >/dev/null; }
"$ADB" shell settings put global sysui_demo_allowed 1
demo enter
demo battery -e level 100 -e plugged false
demo network -e wifi show -e level 4 -e fully true
demo network -e mobile show -e level 4 -e datatype none -e fully true
demo notifications -e visible false
aclock() { demo clock -e hhmm "$(date +%H%M)"; }
"$ADB" emu geo fix "$MAP_LON" "$MAP_LAT"
"$ADB" shell am force-stop $BUNDLE
"$ADB" shell am start -n $BUNDLE/.MainActivity --ez csResetPlaces true --ez csResetPrefs true >/dev/null
sleep 18; "$ADB" emu geo fix "$MAP_LON" "$MAP_LAT"; sleep 4; aclock; sleep 2
"$ADB" exec-out screencap -p > "$OUT/final-android-map.png"
"$ADB" shell am force-stop $BUNDLE; sleep 1
"$ADB" shell am start -n $BUNDLE/.MainActivity --ez csAutoDrive true >/dev/null
sleep 45; aclock; sleep 2
"$ADB" exec-out screencap -p > "$OUT/final-android-nav.png"
demo exit

python - "$OUT" <<'PY'
import glob, os, sys
from PIL import Image
for f in glob.glob(os.path.join(sys.argv[1], "final-*.png")):
    im = Image.open(f).convert("RGB")
    im.thumbnail((640, 640 * 3))
    im.save(f[:-4] + ".webp", "WEBP", quality=84, method=6)
PY
ls -la "$OUT"
