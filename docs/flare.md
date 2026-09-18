# Flare: an open protocol for road alert sources

Flare is the protocol CommuteScout uses to talk to third-party alert
sources, called plugins. A plugin is a server, not an app: it answers a
handful of HTTPS requests, so it works the same for the web map, the iOS
app, the Android app, and anything else that speaks the protocol. Anyone
can run a plugin for themselves (private), for a group (unlisted), or for
everyone (public, listed in the catalog).

This document is the specification. Version 1. Additive changes only
within version 1; the version is in every path.

## What a plugin can do

| Capability | What it means |
|---|---|
| `alerts` | Serve alerts near a point. Required. |
| `report` | Accept a new report from a user (police, crash, hazard, and the rest). |
| `confirm` | Accept a "still there" or "not there" vote on an alert. |
| `notify` | Mark alerts the app should announce out loud and push, not just draw. |

A plugin declares what it supports in its handshake. The apps only ask for
what a plugin declared.

## Who talks to whom

Two topologies. The manifest chooses; a public plugin is always mediated.

**Mediated.** The CommuteScout backend polls the plugin's `alerts` per grid
cell, validates and caps what comes back, and serves it through the same
snapshot the map and apps already read. User reports and confirmations go
to the backend, which forwards them to the plugin under CommuteScout's own
identity. The plugin never sees a user, a device, an address or an exact
position. Abuse control is CommuteScout's.

**Direct.** The app calls the plugin itself. This is for private plugins
only: something a person runs on their own network for their own devices.
The app sends the user's snapped grid tile, never the exact position, and
sends no account identifiers; the plugin may require its own bearer token
(set once in the app). Direct plugins can show anything, including
personal data, because nothing leaves the user's own path.

## Vocabulary

Positions are decimal degrees, WGS 84. Distances are meters. Times are
ISO 8601 with an offset. Identifiers are strings the plugin chooses and
keeps stable for the life of the record.

### Alert kinds

Every alert carries one `kind` from this list. The list is the union of
what Waze, SABRE and the state feeds distinguish; a plugin may use any
subset.

```
POLICE_VISIBLE   POLICE_HIDING    POLICE_OTHER
CRASH_MINOR      CRASH_MAJOR
HAZARD_ON_ROAD   HAZARD_OBJECT    HAZARD_POTHOLE   HAZARD_ANIMAL
HAZARD_CONSTRUCTION
HAZARD_SHOULDER  HAZARD_SHOULDER_CAR   HAZARD_SHOULDER_ANIMAL
WEATHER_FLOOD    WEATHER_FOG      WEATHER_ICE      WEATHER_HAIL
WEATHER_SNOW
ROAD_CLOSED      LANE_CLOSED      RAMP_CLOSED
JAM_MODERATE     JAM_HEAVY        JAM_STANDSTILL
CHAINS_REQUIRED  CHAINS_NOT_REQUIRED
CAMERA_SPEED     CAMERA_RED_LIGHT CAMERA_ISSUE
MAP_ISSUE        OTHER
```

### Alert record

```json
{
  "id": "sabreplus:2026-09-16:8f3a",
  "kind": "POLICE_VISIBLE",
  "lat": 37.3382,
  "lon": -121.8863,
  "heading_deg": 270,
  "road_names": ["I-280 N"],
  "description": "CHP on the right shoulder past Meridian",
  "report_ts": "2026-09-16T18:04:11-07:00",
  "confirm_ts": "2026-09-16T18:21:02-07:00",
  "n_confirmations": 3,
  "reliability": 0.8,
  "ttl_s": 1800,
  "notify": true,
  "geometry": {"type": "LineString", "coordinates": [[-121.89, 37.34], [-121.87, 37.35]]},
  "source_url": "https://example.com/alerts/8f3a",
  "extra": {"unit": "CHP 42"}
}
```

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Stable within the plugin. Confirmations and updates refer to it. |
| `kind` | yes | One of the kinds above. Unknown kinds are dropped. |
| `lat`, `lon` | yes | Where the alert is. For a stretch, the start. |
| `heading_deg` | no | Direction of travel it applies to, 0 to 359. Omit for both directions. |
| `road_names` | no | Road names as signed, most specific first. |
| `description` | no | One sentence for a person. At most 200 characters. |
| `report_ts` | yes | When it was first reported. |
| `confirm_ts` | no | When it was last confirmed. |
| `n_confirmations` | no | Count of confirmations, 0 if none. |
| `reliability` | no | 0 to 1, the plugin's own confidence. Default 0.5. |
| `ttl_s` | yes | Seconds from `report_ts` (or `confirm_ts` when present) after which the alert is stale. At most 86400. |
| `notify` | no | The app should announce it (voice, push) when the driver is approaching. Needs the `notify` capability. |
| `geometry` | no | GeoJSON Point or LineString when the alert covers a stretch. At most 500 points. |
| `source_url` | no | Where a person can read more. |
| `extra` | no | Anything else, at most 2 KB, shown in the details pane as key: value. |

A response is capped at 500 alerts and 1 MB. A plugin that has more
should return the nearest 500.

## Endpoints

All paths are relative to the plugin's `base`, which must be `https://`.
Every response is `application/json; charset=utf-8`. Every request carries
`Accept: application/json` and a `User-Agent` naming the caller.

### GET /flare/v1/handshake

Who the plugin is and what it can do. Cached by callers for an hour.

```json
{
  "protocol": "flare/1",
  "id": "sabreplus",
  "name": "SABRE Plus (CHP + Waze)",
  "version": "2.1.0",
  "capabilities": {"alerts": true, "report": true, "confirm": true, "notify": true},
  "kinds": ["POLICE_VISIBLE", "POLICE_HIDING", "CRASH_MAJOR", "HAZARD_ON_ROAD"],
  "coverage": {"bbox": [32.5, -124.5, 42.0, -114.1]},
  "refresh_s": 60,
  "attribution": {"name": "SABRE Plus", "url": "https://example.com"},
  "contact": "mailto:owner@example.com",
  "auth": "none"
}
```

`auth` is `none`, or `bearer` when the plugin wants a token on every other
call (private plugins). `coverage.bbox` is `[south, west, north, east]`;
callers never ask outside it. `refresh_s` is the polling hint; callers
honor it and never poll faster than 15 seconds.

### GET /flare/v1/alerts?lat&lon&r

Alerts within `r` meters of the point. `r` is at most 100000. Mediated
callers pass grid-cell centers; direct callers pass the snapped tile
center, never the raw position.

```json
{"alerts": [ ...alert records... ], "ttl_s": 60, "as_of": "2026-09-16T18:30:00-07:00"}
```

`ttl_s` is how long the caller may cache this response. `as_of` is when
the plugin last refreshed its own data.

### POST /flare/v1/report

A new report from a user. Needs the `report` capability.

```json
{
  "kind": "HAZARD_ON_ROAD",
  "lat": 37.34, "lon": -121.88,
  "heading_deg": 270,
  "ts": "2026-09-16T18:40:00-07:00",
  "description": "Ladder in the number 2 lane",
  "reporter": "r:9d2c8f...",
  "client": "commutescout-ios/1.0"
}
```

`reporter` is an opaque, per-plugin, stable pseudonym the caller derives
from the account (a keyed hash); it never identifies the person and the
plugin can still rate-limit and score a reporter. Mediated calls come from
CommuteScout, which has already applied its caps and attestation; a
plugin may apply its own on top.

Response: `201` with `{"id": "...", "alert": {...}}` when accepted,
`202` with `{"queued": true}` when the plugin will decide later, `422`
with the error envelope when refused (for example too far from a road).

### POST /flare/v1/confirm

```json
{"alert_id": "sabreplus:2026-09-16:8f3a", "vote": "up", "ts": "...", "reporter": "r:9d2c8f..."}
```

`vote` is `up` (still there) or `gone` (not there). Response `200` with
the updated alert, or `404` when the alert is unknown.

### Errors

The same envelope CommuteScout's API uses:

```json
{"error": {"code": "outside_coverage", "message": "...", "hint": "..."}}
```

Codes a plugin may use: `bad_request`, `unauthorized`, `outside_coverage`,
`too_far_from_road`, `rate_limited` (with `Retry-After`), `unknown_alert`,
`unavailable`. Unknown codes are treated as `bad_request`.

## Manifest

What a plugin looks like in the catalog and in the app's sources list.

```json
{
  "id": "sabreplus",
  "name": "SABRE Plus (CHP + Waze)",
  "base": "https://plugins.example.com",
  "protocol": "flare/1",
  "visibility": "public",
  "trust": "community",
  "attribution": {"name": "SABRE Plus", "url": "https://example.com"},
  "signature": "<reserved; not issued or verified yet>"
}
```

`signature` is reserved for a JWS that CommuteScout will issue for
verified entries. Nothing issues or checks one today: the map, the
apps, and the backend do not read the field, and its presence proves
nothing.

`visibility` is `public` (listed, always mediated), `unlisted` (mediated,
reachable by id), or `private` (direct; the user typed the URL). `trust`
is `official`, `verified`, `community` or `private`; it decides whether
`notify` alerts may speak (official and verified: yes; community: map
only until promoted; private: the user's choice).

## Three tiers

Every plugin is shown to people as one of three levels, derived from the
manifest (`ca_roads.flare.tier_of`) and carried on every marker and
catalog row as `tier`:

| Tier | Manifest | What it means |
|---|---|---|
| `approved` | `visibility: public`, `trust: official` or `verified` | Reviewed by CommuteScout: the operator is known and the feed passed review. Drawn by default, may speak (`notify`), badged "approved". |
| `unreviewed` | `visibility: public` or `unlisted`, `trust: community` | Anyone who passes the conformance check can be listed. Drawn and labelled "public, not reviewed"; never speaks unless the user turns voice on for that source. |
| `private` | `visibility: private` (added by URL on one device) | Direct from the phone to the plugin. Whatever the user wants, including voice; nothing leaves the user's own path. |

Official agency data (the state feeds) is not a plugin and always
outranks all three.

## Rules for callers

- Never send a user's exact position to a plugin. Mediated: grid-cell
  centers. Direct: the snapped tile center.
- Never send an account identifier; `reporter` is a per-plugin pseudonym.
- Honor `refresh_s`, `ttl_s`, `coverage.bbox` and `Retry-After`.
- Drop alerts with unknown `kind`, no `ttl_s`, or past their `ttl_s`.
- Cap what one plugin can show: 500 alerts per response, 50 per grid
  cell, 1 MB per response; a plugin over the caps is trimmed, not refused.
- Official agency data always outranks plugin alerts on the same spot.

## Rules for plugins

- Serve over HTTPS with a valid certificate. Answer the handshake without
  authentication.
- Keep `id` stable for the life of an alert; reuse means an update.
- Set `ttl_s` honestly; stale alerts are the fastest way to lose trust.
- Do not log the callers' addresses beyond what abuse control needs.
- Say who you are: `attribution` and `contact` in the handshake.

## Conformance

`python -m ca_roads.flare check https://plugins.example.com` runs the
conformance suite against a live plugin: handshake shape, an alerts call
inside the coverage box, every alert validated against this document, the
caps, and, when declared, a report and a confirm round trip with a clearly
marked test record. A plugin listed in the catalog passes it on every
release.
