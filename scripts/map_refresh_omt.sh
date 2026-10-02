#!/usr/bin/env bash
# Refresh the second set of base map files: the United States in the
# OpenMapTiles layout, which the Positron and Bright styles draw from.
#
# OpenFreeMap publishes its whole planet as one PMTiles file, the same
# tiles its hosted service serves. A one-off VM cuts the United States
# out of it over HTTP (only the tiles needed are read), then every
# state, uploads them beside the Protomaps-layout files under map/omt/,
# and removes itself. About half an hour, well under a dollar. Check the
# log afterwards:
#   gcloud storage cat gs://data.commutescout.com/map/omt/_refresh.log
#
#   scripts/map_refresh_omt.sh                      # the version being served now
#   scripts/map_refresh_omt.sh 20260927_080001_pt   # a specific one
set -euo pipefail
PROJECT=ca-roads-mcp
ZONE=us-west1-b
BUCKET=gs://data.commutescout.com/map/omt
# The version OpenFreeMap is serving is the dated folder in its tile address.
BUILD="${1:-$(curl -s https://tiles.openfreemap.org/planet | python -c 'import json,sys; print(json.load(sys.stdin)["tiles"][0].split("/planet/")[1].split("/")[0])')}"
echo "build $BUILD"
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
# gcloud on Windows is a native program: it needs the Windows spelling of
# a Git Bash path.
if command -v cygpath >/dev/null; then TMPW="$(cygpath -w "$TMP")"; else TMPW="$TMP"; fi
cp "$HERE/../src/ca_roads_demo/static/us-states.json" "$TMP/us-states.json"
cp "$HERE/map_states.py" "$TMP/map_states.py"

cat > "$TMP/startup.sh" <<EOF
#!/bin/bash
# Everything logs to a file, never a pipe: a pipe closing is what killed
# the first run of the other refresh.
exec > /root/refresh.log 2>&1 < /dev/null
set -u
BUILD=$BUILD
cd /root
echo "start \$(date -u +%FT%TZ) build \$BUILD"
# Whatever happens, the log lands in the bucket and the VM goes away.
# Powering off is what removes it: the VM is created to be deleted when
# it stops, and after two hours regardless.
finish() {
  echo "finish \$(date -u +%FT%TZ)"
  gcloud storage cp /root/refresh.log "$BUCKET/_refresh.log"
  shutdown -h now
}
trap finish EXIT
apt-get update -qq >/dev/null && apt-get install -y -qq curl ca-certificates python3 >/dev/null
curl -sL -o pmtiles.tar.gz https://github.com/protomaps/go-pmtiles/releases/download/v1.31.2/go-pmtiles_1.31.2_Linux_x86_64.tar.gz
tar xzf pmtiles.tar.gz && chmod +x pmtiles && ./pmtiles version
curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/us-states" > us-states.json
curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/map-states-py" > map_states.py
cat > us.geojson <<'GEO'
{"type":"Feature","properties":{},"geometry":{"type":"MultiPolygon","coordinates":[
 [[[-125.6,24.2],[-66.6,24.2],[-66.6,49.6],[-125.6,49.6],[-125.6,24.2]]],
 [[[-180.0,51.0],[-129.0,51.0],[-129.0,72.0],[-180.0,72.0],[-180.0,51.0]]],
 [[[-161.0,18.5],[-154.5,18.5],[-154.5,22.5],[-161.0,22.5],[-161.0,18.5]]]
]}}
GEO
T0=\$(date +%s)
./pmtiles extract "https://btrfs.openfreemap.com/areas/planet/\$BUILD/tiles.pmtiles" us.pmtiles --region=us.geojson --maxzoom=14 --download-threads=8
echo "us extract exit \$? after \$(( \$(date +%s) - T0 )) s: \$(ls -la us.pmtiles)"
[ -s us.pmtiles ] || exit 1
./pmtiles show us.pmtiles | head -20
gcloud storage cp us.pmtiles "$BUCKET/us-\$BUILD.pmtiles" --cache-control="public, max-age=86400" && echo "uploaded us-\$BUILD"
python3 map_states.py us-states.json us.pmtiles "\$BUILD"
gcloud storage cp states/*.pmtiles "$BUCKET/states/" --cache-control="public, max-age=86400" && echo "states uploaded"
# The stable names last, so a client never sees a half-replaced set.
gcloud storage cp "$BUCKET/us-\$BUILD.pmtiles" "$BUCKET/us.pmtiles" && echo "us.pmtiles now \$BUILD"
gcloud storage cp index.json "$BUCKET/index.json" --cache-control="public, max-age=600" && echo "index uploaded"
echo "done \$(date -u +%FT%TZ)"
EOF

gcloud compute instances create map-refresh-omt --project "$PROJECT" --zone "$ZONE" \
  --machine-type e2-highmem-8 --boot-disk-size 200GB --boot-disk-type pd-balanced \
  --image-family debian-12 --image-project debian-cloud \
  --instance-termination-action DELETE --max-run-duration 2h \
  --service-account 15002631928-compute@developer.gserviceaccount.com --scopes cloud-platform \
  --metadata-from-file "startup-script=$TMPW/startup.sh,us-states=$TMPW/us-states.json,map-states-py=$TMPW/map_states.py"
echo "VM map-refresh-omt started; it removes itself when done, or after two hours."
echo "The log lands at $BUCKET/_refresh.log when it finishes."
