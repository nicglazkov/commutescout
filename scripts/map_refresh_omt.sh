#!/usr/bin/env bash
# Build the second set of base map files: the United States in the
# OpenMapTiles layout, which the Positron and Bright styles draw from.
#
# map_refresh.sh cuts the Protomaps-layout files (Slate, Gray, Dark) out
# of a ready-made world build. Nobody publishes a ready-made
# OpenMapTiles build to cut from, so this one makes it: a one-off VM
# downloads the OpenStreetMap extract for the United States, runs
# Planetiler's OpenMapTiles profile over it, cuts every state, uploads
# the lot beside the others under map/omt/, and deletes itself. About an
# hour and a half, around a dollar. Check the log afterwards:
#   gcloud storage cat gs://data.commutescout.com/map/omt/_refresh.log
#
#   scripts/map_refresh_omt.sh
set -euo pipefail
PROJECT=ca-roads-mcp
ZONE=us-west1-b
BUCKET=gs://data.commutescout.com/map/omt
PLANETILER="${PLANETILER:-0.10.2}"
BUILD="$(date -u +%Y%m%d)"
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
echo "start \$(date -u +%FT%TZ) build \$BUILD planetiler $PLANETILER"
# Whatever happens, the log lands in the bucket and the VM goes away.
# Powering off is what removes it: the VM is created to be deleted when
# it stops, and after four hours regardless.
finish() {
  echo "finish \$(date -u +%FT%TZ)"
  gcloud storage cp /root/refresh.log "$BUCKET/_refresh.log"
  shutdown -h now
}
trap finish EXIT
apt-get update -qq >/dev/null && apt-get install -y -qq curl ca-certificates python3 >/dev/null
curl -sL -o jdk.tar.gz "https://api.adoptium.net/v3/binary/latest/21/ga/linux/x64/jdk/hotspot/normal/eclipse"
mkdir jdk && tar xzf jdk.tar.gz -C jdk --strip-components=1 && ./jdk/bin/java -version
curl -sL -o planetiler.jar "https://github.com/onthegomap/planetiler/releases/download/v$PLANETILER/planetiler.jar"
ls -la planetiler.jar
curl -sL -o pmtiles.tar.gz https://github.com/protomaps/go-pmtiles/releases/download/v1.31.2/go-pmtiles_1.31.2_Linux_x86_64.tar.gz
tar xzf pmtiles.tar.gz && chmod +x pmtiles && ./pmtiles version
curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/us-states" > us-states.json
curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/map-states-py" > map_states.py
T0=\$(date +%s)
# The extract comes down with curl, which retries and resumes; Planetiler's
# own downloader gave up on Geofabrik after one slow answer.
mkdir -p data/sources
for url in https://download.geofabrik.de/north-america/us-latest.osm.pbf \\
           https://ftp5.gwdg.de/pub/misc/openstreetmap/download.geofabrik.de/north-america/us-latest.osm.pbf; do
  curl -L --fail --retry 8 --retry-delay 20 --retry-all-errors -C - -o data/sources/us.osm.pbf "\$url" && break
done
echo "extract: \$(ls -la data/sources/us.osm.pbf) after \$(( \$(date +%s) - T0 )) s"
./jdk/bin/java -Xmx24g -jar planetiler.jar --download --osm-path=data/sources/us.osm.pbf --output=us.pmtiles \\
  --maxzoom=14 --languages=en --nodemap-type=sparsearray --storage=mmap --force
echo "planetiler exit \$? after \$(( \$(date +%s) - T0 )) s: \$(ls -la us.pmtiles)"
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
  --machine-type e2-highmem-8 --boot-disk-size 300GB --boot-disk-type pd-ssd \
  --image-family debian-12 --image-project debian-cloud \
  --instance-termination-action DELETE --max-run-duration 4h \
  --service-account 15002631928-compute@developer.gserviceaccount.com --scopes cloud-platform \
  --metadata-from-file "startup-script=$TMPW/startup.sh,us-states=$TMPW/us-states.json,map-states-py=$TMPW/map_states.py"
echo "VM map-refresh-omt started; it deletes itself when done, or after four hours."
echo "The log lands at $BUCKET/_refresh.log when it finishes."
