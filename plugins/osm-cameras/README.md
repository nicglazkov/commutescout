# Speed and red light cameras (OpenStreetMap)

A read-only [Flare](../../docs/flare.md) plugin that serves fixed speed
and red light cameras in the United States, as mapped by OpenStreetMap
contributors.

- Kinds: `CAMERA_SPEED`, `CAMERA_RED_LIGHT`.
- Capabilities: `alerts` only. Nothing is reported to it or confirmed
  through it, and it never asks the apps to speak.
- Coverage is whatever has been mapped: good in some cities, thin in
  others. A wrong or missing camera is fixed on openstreetmap.org; every
  alert links to its record there.

## How it works

`refresh.py` runs one Overpass query and writes `cameras.json`. The
service loads that file at start and answers from memory, so it has no
upstream to wait on and starts in about a second.

```
python refresh.py          # rebuild cameras.json (monthly, with the map files)
python server.py           # serve on :8310
python -m ca_roads.flare check http://127.0.0.1:8310
```

## Deploy

```
gcloud run deploy osm-cameras --source plugins/osm-cameras \
  --project ca-roads-mcp --region us-west1 \
  --memory 256Mi --cpu 1 --min-instances 0 --max-instances 1 \
  --allow-unauthenticated
```

It scales to zero, so it costs nothing while nobody asks.

## Data

(c) OpenStreetMap contributors, under the Open Database License. See
https://www.openstreetmap.org/copyright.
