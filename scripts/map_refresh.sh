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
# Any failed step stops the run before a bad file can reach the stable
# names; the trap below still ships the log and powers the VM off.
set -eu
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
./pmtiles extract "https://build.protomaps.com/\$BUILD.pmtiles" us.pmtiles --region=us.geojson --maxzoom=15 --download-threads=8
echo "us extract done after \$(( \$(date +%s) - T0 )) s: \$(ls -la us.pmtiles)"
# A truncated file must never be promoted to the stable name every app
# and the site read: it has to exist, have a size, and parse.
[ -s us.pmtiles ] || { echo "us.pmtiles is empty"; exit 1; }
./pmtiles show us.pmtiles | head -20
gcloud storage cp us.pmtiles "$BUCKET/us-\$BUILD.pmtiles" --cache-control="public, max-age=86400" && echo "uploaded us-\$BUILD"
python3 map_states.py us-states.json us.pmtiles "\$BUILD"
gcloud storage cp states/*.pmtiles "$BUCKET/states/" --cache-control="public, max-age=86400" && echo "states uploaded"
# The stable names last, so a client never sees a half-replaced set.
gcloud storage cp "$BUCKET/us-\$BUILD.pmtiles" "$BUCKET/us.pmtiles" && echo "us.pmtiles now \$BUILD"
gcloud storage cp index.json "$BUCKET/index.json" --cache-control="public, max-age=600" && echo "index uploaded"
# Cloudflare R2 is what the site and the apps read from (maps.commutescout.com,
# no egress charge); GCS keeps a copy. The same files go there, the stable
# names last. Keys come from Secret Manager, which the VM's account can read.
curl -sSL https://rclone.org/install.sh | bash >/dev/null 2>&1 || true
tok() { curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token" | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])'; }
secret() { curl -s -H "Authorization: Bearer \$(tok)" "https://secretmanager.googleapis.com/v1/projects/ca-roads-mcp/secrets/\$1/versions/latest:access" | python3 -c 'import sys,json,base64;print(base64.b64decode(json.load(sys.stdin)["payload"]["data"]).decode().strip())'; }
mkdir -p /root/.config/rclone
printf '[r2]\ntype = s3\nprovider = Cloudflare\naccess_key_id = %s\nsecret_access_key = %s\nendpoint = %s\nacl = private\nno_check_bucket = true\n' "\$(secret r2-access-key-id)" "\$(secret r2-secret-access-key)" "\$(secret r2-endpoint)" > /root/.config/rclone/rclone.conf
R2=r2:commutescout-maps
# The same Cache-Control the GCS copies carry, so the edge revalidates a
# day after a refresh and the index within ten minutes.
PM="--header-upload=Cache-Control: public, max-age=86400"
rclone copyto us.pmtiles "\$R2/us-\$BUILD.pmtiles" --s3-chunk-size 64M --s3-upload-concurrency 8 "\$PM" && echo "r2: uploaded us-\$BUILD"
rclone copy states "\$R2/states" --transfers 8 --s3-chunk-size 64M "\$PM" && echo "r2: states uploaded"
rclone copyto "\$R2/us-\$BUILD.pmtiles" "\$R2/us.pmtiles" "\$PM" && echo "r2: us.pmtiles now \$BUILD"
rclone copyto index.json "\$R2/index.json" "--header-upload=Cache-Control: public, max-age=600" && echo "r2: index uploaded"
rclone check . "\$R2" --one-way --size-only --include "us.pmtiles" --include "index.json" --include "states/**" 2>&1 | tail -2
echo "done \$(date -u +%FT%TZ)"
EOF

gcloud compute instances create map-refresh --project "$PROJECT" --zone "$ZONE" \
  --machine-type e2-standard-4 --boot-disk-size 200GB --boot-disk-type pd-balanced \
  --image-family debian-12 --image-project debian-cloud \
  --instance-termination-action DELETE --max-run-duration 2h \
  --service-account 15002631928-compute@developer.gserviceaccount.com --scopes cloud-platform \
  --metadata-from-file "startup-script=$TMP/startup.sh,us-states=$TMP/us-states.json,map-states-py=$TMP/map_states.py"
echo "VM map-refresh started; it removes itself when done, or after two hours."
echo "The log lands at $BUCKET/_refresh.log when it finishes."
