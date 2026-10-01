"""On the refresh VM: cut every state out of us.pmtiles and write index.json.

Usage: python3 map_states.py us-states.json us.pmtiles 20261001
"""
import json
import os
import subprocess
import sys
import time

shapes, source, build = sys.argv[1], sys.argv[2], sys.argv[3]
CODES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}
os.makedirs("states", exist_ok=True)
with open(shapes, encoding="utf-8") as f:
    features = json.load(f)["features"]
index = []
for feature in features:
    name = feature["properties"].get("NAME") or feature["properties"].get("name")
    code = CODES.get(name)
    if not code:
        continue
    region = f"states/{code}.geojson"
    with open(region, "w", encoding="utf-8") as f:
        json.dump({"type": "Feature", "properties": {}, "geometry": feature["geometry"]}, f)
    out = f"states/{code}.pmtiles"
    t0 = time.time()
    r = subprocess.run(["./pmtiles", "extract", source, out, f"--region={region}", "--maxzoom=15"],
                       capture_output=True, text=True, check=False)
    if r.returncode != 0:
        print(code, "FAILED", r.stdout[-300:], r.stderr[-300:], flush=True)
        continue
    size = os.path.getsize(out)
    print(f"{code} {size / 1e9:.2f} GB in {time.time() - t0:.0f} s", flush=True)
    index.append({"code": code, "name": name, "bytes": size})
index.sort(key=lambda s: s["name"])
with open("index.json", "w", encoding="utf-8") as f:
    json.dump({"build": build, "us_bytes": os.path.getsize(source), "states": index,
               "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, f, indent=1)
print("index written:", len(index), "states")
