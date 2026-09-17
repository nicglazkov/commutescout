# Plan: an unofficial Waze (and Google) plugin for Flare

A rough plan and wireframe for pulling crowd-sourced reports from Waze
(and what is and is not possible from Google Maps) into CommuteScout as
a Flare plugin. It is written so the plugin can be built as a separate
service later, without touching the map, the apps or the backend, which
already speak Flare. Reference implementation for the shape of the work:
Nic's highway-radar-sabre-plus, which does the same for a radar app.

## Where it lands in the three tiers

- Ships as **public, unreviewed** first (`trust: community`), because
  the data is scraped from a third party under its own terms, not
  licensed. It is drawn and labelled "public, not reviewed" and never
  speaks unless a user turns voice on for it.
- Anyone can also run it **privately** for their own devices (the same
  code, `FLARE_TOKEN` set, added by URL in the app).
- It becomes **approved** only if a data agreement exists. Until then
  the catalog entry names the operator and links to this plan.

## What Waze offers, and the gray zone

Waze has no public API for reports. Its live map fetches a GeoRSS-style
JSON feed per viewport (`live-map/api/georss` with a bounding box and
`types=alerts,traffic`) that carries two lists:

- `alerts`: type (`POLICE`, `ACCIDENT`, `HAZARD`, `JAM`, `ROAD_CLOSED`,
  `WEATHERHAZARD`...), subtype (`HAZARD_ON_SHOULDER_CAR_STOPPED`,
  `POLICE_VISIBLE`, `ACCIDENT_MAJOR`...), location, street, reliability
  (0 to 10), confidence, thumbs up, report time, a UUID, and the
  reporter's rating.
- `jams`: polylines with speed, delay and level (1 to 5).

The feed is what the browser map uses, not a supported product. Terms of
service forbid scraping for commercial use; there is no key, no quota
contract, and the shape can change any day. That is the gray zone Nic
named: the plugin is an external, unofficial source that a person or
group adds knowingly, never a CommuteScout data source. The public
listing says so in its attribution and never uses the Waze name as its
own. Volume stays low (one fetch per grid cell per minute, cells the
size of a county, cached), which is far below what a single open browser
tab generates.

Google Maps has no crowd-report feed at all. What Google does license is
traffic: the Routes API returns traffic-aware ETAs and speed-band
polylines under a key and a bill. That is not a plugin; it is the
Stadia Standard flip's competitor for ETAs, and it stays parked with it.
A "Google" plugin would only ever carry jams, so this plan is Waze-first.

## Architecture (wireframe)

```
 Waze live-map feed  ──(HTTPS, per county cell, 60 s, cached)──▶  wz-flare (Cloud Run, 1 instance)
                                                                     │  /flare/v1/handshake
                                                                     │  /flare/v1/alerts?lat&lon&r
                                                                     │  /flare/v1/confirm     (in-memory votes)
                                                                     │  (no /report: Waze accepts none)
                                                                     ▼
                                    CommuteScout backend (mediated, public unreviewed)
                                    ────────────────────────────────────────────────
                                    web map  ·  iOS  ·  Android   (drawn as "public, not reviewed")

 Private mode: the phone calls wz-flare directly with FLARE_TOKEN; nothing goes through CommuteScout.
```

One file, the same skeleton as `examples/flare-plugin/server.py`:

1. **Cell poller.** Divide the coverage box (California to start, then
   any state the person runs it for) into 1° cells. Every `refresh_s`
   (60 s), fetch each cell that a caller asked about in the last 10
   minutes; idle cells are not fetched. Keep the last good result per
   cell with its time; serve stale-with-a-flag for up to 5 minutes on
   errors, then drop.
2. **Mapping.** Waze `type/subtype` to Flare kinds (table below);
   `reliability/10` to `reliability`; `nThumbsUp` to `n_confirmations`;
   `pubMillis` to `report_ts`; street to `road_names`; jams to
   `JAM_MODERATE/HEAVY/STANDSTILL` by level with the polyline as
   `geometry`. `ttl_s`: 20 min for police and hazards, 45 min for
   crashes, 60 min for closures, jam TTL = 5 min. `id` =
   `wz:<uuid>`; the same UUID across polls is an update, not a new alert.
3. **Confirm.** `up` and `gone` votes are kept in memory per alert id
   and folded into `n_confirmations` and `reliability` for the next
   response; Waze itself gets nothing. `gone` votes past a threshold
   hide the alert for that plugin.
4. **Report.** Not offered (`capabilities.report: false`). Reports stay
   with CommuteScout's own community source, which the map and apps
   already use. If Waze ever exposes a report endpoint, the plugin gains
   it without any app change.
5. **Handshake.** `coverage.bbox` = the configured states,
   `refresh_s: 60`, `attribution: {name: "Unofficial Waze relay
   (community)", url: <the operator's page>}`, `auth: none` public or
   `bearer` private.

### Kind mapping

| Waze type / subtype | Flare kind |
|---|---|
| POLICE / POLICE_VISIBLE | POLICE_VISIBLE |
| POLICE / POLICE_HIDING | POLICE_HIDING |
| POLICE / other | POLICE_OTHER |
| ACCIDENT / ACCIDENT_MINOR | CRASH_MINOR |
| ACCIDENT / ACCIDENT_MAJOR, none | CRASH_MAJOR |
| HAZARD / HAZARD_ON_ROAD_* (object, pothole, construction) | HAZARD_OBJECT, HAZARD_POTHOLE, HAZARD_CONSTRUCTION |
| HAZARD / HAZARD_ON_SHOULDER_CAR_STOPPED | HAZARD_SHOULDER_CAR |
| HAZARD / HAZARD_ON_SHOULDER_ANIMALS | HAZARD_SHOULDER_ANIMAL |
| HAZARD / HAZARD_ON_ROAD (generic) | HAZARD_ON_ROAD |
| WEATHERHAZARD / *FOG, *FLOOD, *ICE, *HAIL, *SNOW | WEATHER_FOG, WEATHER_FLOOD, WEATHER_ICE, WEATHER_HAIL, WEATHER_SNOW |
| ROAD_CLOSED / ROAD_CLOSED_EVENT, CONSTRUCTION | ROAD_CLOSED |
| ROAD_CLOSED / ROAD_CLOSED_HAZARD | ROAD_CLOSED |
| JAM level 1-2, 3-4, 5 | JAM_MODERATE, JAM_HEAVY, JAM_STANDSTILL |
| anything else | OTHER |

## How it shows up

- **Web map**: markers in the Community layer; popup reads "Community
  report · Source: Unofficial Waze relay (public, not reviewed)", with
  the reliability and thumbs-up count Waze gave.
- **Apps**: the Sources screen lists it under "Public plugins (not
  reviewed)" with a switch; the marker card shows the same source line;
  Advanced alerts lets a person turn voice on for police reports from
  it if they want that.
- **Private**: add the URL and token under My plugins; it is read
  straight from the phone.

## Steps and effort

1. Server skeleton from the example plugin, cell poller, mapping table,
   conformance check passing locally: one day.
2. Cloud Run deploy (same flags as the demo service, one instance, tiny
   memory), health and stale-data alarms, a status page line: half a
   day.
3. Manifest submitted through the contact page, listed as unreviewed;
   confirm votes wired: half a day.
4. Watch it for a week: feed-shape changes, ban behavior, volume.

Not in scope: writing reports to Waze, Google crowd reports (none
exist), and using either company's name or branding for the plugin.
