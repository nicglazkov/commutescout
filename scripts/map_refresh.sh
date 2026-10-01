#!/usr/bin/env bash
# Rebuild the base map files from the newest Protomaps world build.
#
# Creates a one-off VM in us-west1 that cuts the United States (lower 48,
# Alaska, Hawaii) at full detail out of the world build, then every
# state, uploads them to the data bucket with an index, and deletes
# itself. Run about monthly; a run takes 30 to 60 minutes and costs
# well under a dollar. Check the log in the bucket afterwards:
#   gcloud storage cat gs://data.commutescout.com/map/_refresh.log
#
#   scripts/map_refresh.sh            # newest build
#   scripts/map_refresh.sh 20261001   # a specific build
#
# What it needs: the Compute Engine API on, and the default compute
# service account able to write the bucket (it has Cloud Build's role,
# which covers that). Nothing on this machine but gcloud.
set -euo pipefail
PROJECT=ca-roads-mcp
ZONE=us-west1-b
BUCKET=gs://data.commutescout.com/map
BUILD="${1:-$(curl -s https://build-metadata.protomaps.dev/builds.json | python -c 'import json,sys; print(json.load(sys.stdin)[-1]["key"].split(".")[0])')}"
echo "build $BUILD"
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
cp "$HERE/../src/ca_roads_demo/static/us-states.json" "$TMP/us-states.json"
cp "$HERE/map_states.py" "$TMP/map_states.py"

cat > "$TMP/startup.sh" <<EOF
#!/bin/bash
# Everything logs to a file, never a pipe: a pipe closing is what killed
# the first run of this.
exec > /root/refresh.log 2>&1 < /dev/null
set -u
BUILD=$BUILD
cd /root
echo "start \$(date -u +%FT%TZ) build \$BUILD"
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
./pmtiles extract "https://build.protomaps.com/\$BUILD.pmtiles" us.pmtiles --region=us.geojson --maxzoom=15 --download-threads=8
echo "us extract exit \$? after \$(( \$(date +%s) - T0 )) s: \$(ls -la us.pmtiles)"
gcloud storage cp us.pmtiles "$BUCKET/us-\$BUILD.pmtiles" --cache-control="public, max-age=86400" && echo "uploaded us-\$BUILD"
python3 map_states.py us-states.json us.pmtiles "\$BUILD"
gcloud storage cp states/*.pmtiles "$BUCKET/states/" --cache-control="public, max-age=86400" && echo "states uploaded"
# The stable names last, so a client never sees a half-replaced set.
gcloud storage cp "$BUCKET/us-\$BUILD.pmtiles" "$BUCKET/us.pmtiles" && echo "us.pmtiles now \$BUILD"
gcloud storage cp index.json "$BUCKET/index.json" --cache-control="public, max-age=600" && echo "index uploaded"
echo "done \$(date -u +%FT%TZ)"
gcloud storage cp /root/refresh.log "$BUCKET/_refresh.log"
gcloud compute instances delete map-refresh --zone $ZONE --quiet
EOF

gcloud compute instances create map-refresh --project "$PROJECT" --zone "$ZONE" \
  --machine-type e2-standard-4 --boot-disk-size 200GB --boot-disk-type pd-balanced \
  --image-family debian-12 --image-project debian-cloud \
  --service-account 15002631928-compute@developer.gserviceaccount.com --scopes cloud-platform \
  --metadata-from-file "startup-script=$TMP/startup.sh,us-states=$TMP/us-states.json,map-states-py=$TMP/map_states.py"
echo "VM map-refresh started; it deletes itself when done. Watch with:"
echo "  gcloud compute instances get-serial-port-output map-refresh --zone $ZONE --project $PROJECT | grep -i 'extract\\|upload'"
