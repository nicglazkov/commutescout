# Unofficial Waze relay

A [Flare](../../docs/flare.md) plugin that relays crowd-sourced road alerts
(police, crashes, hazards, closures, jams) from Waze to anything that speaks
Flare: the CommuteScout web map, the iOS app, the Android app, or your own
client.

It is a small Starlette service. It holds one anonymous upstream session,
sweeps the one-degree grid cells that callers have asked about in the last
ten minutes, maps what comes back to the Flare vocabulary, and serves it.
It answers for anywhere in the United States; see
[Coverage follows demand](#coverage-follows-demand) for what that does and
does not mean.

The handshake carries a one-line `description` for the marketplace card:
"Crowd reports from Waze: police, crashes, hazards, jams. Unofficial, at
your own risk." A card that shows the name without that second sentence is
showing half of it.

## Read this before you install it

- This plugin is **unofficial, public and unreviewed**. Nobody has vouched
  for it. You install it at your own risk.
- It is **not affiliated with, endorsed by, or supported by Waze or Google**,
  and it never presents their name as its own. It is listed and labelled as
  "Unofficial Waze relay (community)".
- It reaches Waze the same way the
  [highway-radar-sabre-plus](https://github.com/nicglazkov/highway-radar-sabre-plus)
  project does: by emulating the mobile app's private, undocumented protocol
  over an anonymous session. That is not a supported product and it may be
  contrary to Waze's terms of service.
- **It can stop working any day**, without notice, if the protocol changes or
  the traffic is blocked. Treat everything it serves as a hint, never as the
  official picture. Agency data always outranks it.
- It reports only what the upstream already shows to anyone with the app. It
  sends no user position, no account and no device identifier: the poller
  asks about grid-cell centers under its own identity.

## What it serves

| Field | Where it comes from |
|---|---|
| `id` | `wz:<uuid>`, stable for the life of the alert, so a repeat is an update |
| `kind` | The mapping table below |
| `lat`, `lon` | The alert position |
| `heading_deg` | The reported azimuth, left out when it is zero (unknown) |
| `road_names` | The street on the alert's address |
| `report_ts` | When it was first reported |
| `confirm_ts` | When the thumbs-up count was last seen to rise, or when this plugin took an `up` vote |
| `n_confirmations` | Thumbs-up count plus this plugin's own `up` votes |
| `reliability` | 0.5, plus 0.1 a confirmation, capped at 1 |
| `ttl_s` | 20 minutes for police, hazards and weather; 45 for crashes; 60 for closures; 5 for jams |
| `extra` | The raw upstream type and subtype, and the city |

Three things the plan's record has that this one does not:

- **No `geometry`.** The jam polylines in the plan came from the GeoRSS feed,
  which is now blocked. The protocol this plugin speaks sends jams as points.
- **No `reliability` from upstream.** The same feed carried a 0 to 10
  reliability that the protocol does not, so confidence is derived from the
  confirmation count instead.
- **No `notify`.** The plugin marks nothing to be announced out loud. A public
  unreviewed source never speaks unless a person turns voice on for it, and
  that switch lives in the app.

### Kind mapping

The approved table is in
[docs/plugins-waze-google-plan.md](../../docs/plugins-waze-google-plan.md).
`mapping.py` follows it, except where it and
`AlertMapper.java` in highway-radar-sabre-plus disagree, in which case it
follows sabre-plus, because that mapping was written against the live feed:

| Case | The plan | sabre-plus | This plugin |
|---|---|---|---|
| `POLICE` with no subtype | `POLICE_OTHER` | Visible | `POLICE_VISIBLE` |
| `POLICE_WITH_MOBILE_CAMERA` | `POLICE_OTHER` | Hidden, all covert enforcement | `POLICE_HIDING` |
| `ACCIDENT` with no subtype | `CRASH_MAJOR` | Minor unless it says major | `CRASH_MINOR` |

Two places follow neither, and both are because Flare has a kind that neither
source could use:

| Case | sabre-plus | This plugin | Why |
|---|---|---|---|
| `CAMERA` | Hidden police | `CAMERA_SPEED` | sabre-plus folds cameras into police because Highway Radar draws no camera; Flare has the kind, and a red-light camera drawn as a hidden patrol car is wrong |
| `JAM_*`, `ROAD_CLOSED` | A congestion hazard | `JAM_*`, `ROAD_CLOSED` | Same reason: sabre-plus remaps them so Highway Radar draws them at all; Flare has both |

Chit-chat and parking reports are dropped. Anything unrecognized becomes
`OTHER` rather than disappearing.

## Coverage follows demand

The plugin answers for anywhere in the United States. It does not fetch
anywhere in the United States, and the difference is the whole design.

The relay holds **one** upstream session, and that session is stateful and
serialized: one query at a time, one to two seconds each. So how much ground
stays fresh is a straight function of the query rate, and a wide coverage box
cannot change that. What a wide box does change is where the queries are
allowed to go.

Nothing is fetched on a schedule. A one-degree cell is fetched only after
somebody asks about it, and only while somebody has asked in the last ten
minutes. Among those cells, the busiest win: cells are ranked by how many
times they were asked about inside that window, and the top `WAZE_HOT_CELLS`
(eight by default) are the ones the session sweeps. The ranking is
recalculated every thirty seconds rather than on every request, so a sweep in
progress is not thrown away the moment the order shifts.

Within a hot cell, the fetch is a sweep rather than a sample. A one-degree
cell is about 110 km across, the upstream thins a wide viewport hard, and
asking from the cell's center leaves its corners barely covered: Los Angeles,
for one, sits at the edge of its cell. So each cell is divided into a
`WAZE_SUB_CELLS` lattice (two by two by default) and the squares take turns,
stalest first, each fetched with the shrinking-box series around its own
middle. Eight hot cells is thirty-two squares, a full sweep in a minute or
two.

So a quiet night costs nothing at all, and a busy evening spends everything
the one session has on the handful of places people are actually looking at.
Raise `WAZE_HOT_CELLS` and each cell simply comes round less often; run an
instance per region if you want more ground fresh at once.

If no refresh has succeeded for the refresh window plus five minutes, the
plugin serves nothing at all. Stale police and crash alerts presented as
current are worse than no data.

## Running it

```
pip install -r requirements.txt
python server.py
python -m ca_roads.flare check http://127.0.0.1:8300
```

### Privately, for your own devices

Set `FLARE_TOKEN` and the plugin asks for a bearer token on every call but
the handshake. Add its URL and that token under My plugins in the app; the
phone then reads it directly and nothing goes through CommuteScout.

### Settings

| Variable | Default | What it does |
|---|---|---|
| `FLARE_TOKEN` | none | Requires `Authorization: Bearer <token>` on every call but the handshake |
| `FLARE_ID` | `wz-flare` | The plugin id in the handshake |
| `FLARE_NAME` | Unofficial Waze relay (community) | The name shown in the sources list |
| `FLARE_CONTACT` | the contact page | Where to reach the operator |
| `FLARE_ATTRIBUTION_URL` | the plugins page | Where the attribution links |
| `WAZE_BBOX` | `18.0,-168.0,71.5,-66.5` | Coverage, as `south,west,north,east`. The default is the United States |
| `WAZE_HOT_CELLS` | `8` | How many cells the session keeps fresh at once |
| `WAZE_REFRESH_S` | `60` | How often one lattice square comes round again |
| `WAZE_SUB_CELLS` | `2` | The lattice inside one cell, per side; more is finer and costs more |
| `WAZE_SHRINK_STEPS` | `2` | Query boxes per square; more finds smaller alerts and costs more |
| `WAZE_QUERY_BUDGET_S` | `10` | Wall-clock budget for one square's box series |
| `WAZE_RATE_PER_MIN` | `600` | Requests one address may make a minute. A mediated caller asks per grid cell, so this has to fit a few hundred |
| `WAZE_USER_SESSIONS` | off | Let a signed-in phone hold a session of its own. See below |
| `WAZE_USER_SESSIONS_MAX` | `5` | How many of those may exist at once. The rest fall back to the shared feed |
| `WAZE_USER_IDLE_S` | `600` | How long a user session survives without a request |
| `WAZE_USER_POLL_S` | `15` | How often a phone should come back, and the `ttl_s` its answers carry |
| `WAZE_USER_SALT` | random at boot | Keys the hash that stands in for a person. Leave it unset unless you need the keys to outlive a restart |
| `FIREBASE_PROJECT` | `ca-roads-mcp` | Whose sign-in tokens are accepted |
| `WAZE_STATE_FILE` | none | Where to keep the anonymous account, so a restart does not mint another |
| `WAZE_REPORTS` | off | Pass user reports upstream. See below |
| `PORT` | `8300` | The port to listen on |

`WAZE_STATE_FILE` needs somewhere that survives a restart to be worth
setting. On Cloud Run the filesystem does not, so leave it unset there.

### Deploying

```
gcloud run deploy wz-flare --source plugins/waze-relay \
  --project ca-roads-mcp --region us-west1 \
  --memory 512Mi --cpu 1 --min-instances 0 --max-instances 1 \
  --concurrency 40 --allow-unauthenticated
```

Keep `--max-instances 1`: the session, the account and the cache are all in
process, and a second instance means a second anonymous account.

The CommuteScout deployment runs at
`https://wz-flare-15002631928.us-west1.run.app`.

### Listing it in the catalog

Sign in at `/admin` as an administrator, paste the manifest into the Flare
sources box, and submit. The backend validates it, fetches the handshake once
so a typo fails there rather than silently in the poller, and starts polling
it on the next cycle.

```json
{
  "id": "wz-flare",
  "name": "Unofficial Waze relay (community)",
  "base": "https://wz-flare-15002631928.us-west1.run.app",
  "protocol": "flare/1",
  "visibility": "public",
  "trust": "community",
  "attribution": {
    "name": "Unofficial Waze relay (community)",
    "url": "https://commutescout.com/plugins"
  }
}
```

`visibility: public` with `trust: community` is the `unreviewed` tier: drawn
on the map, labelled "public, not reviewed", and silent unless a person turns
voice on for it.

## A session of your own

The relay holds one upstream session for everybody, which is what the web map
and signed-out phones get. A signed-in phone can do better. The upstream
protocol sends each alert **once per session**, so a phone with a session of
its own gets a stream shaped by where that phone is, rather than alerts
arriving mixed in with everyone else's.

That is the highway-radar-sabre-plus model moved one step in from the device,
and the step costs something worth naming. sabre-plus runs on the phone: the
phone's own address, its own account, its own ten-a-day minting cap. Its
traffic looks like one more phone. Run the same thing here and every user's
session leaves from **one** address on **one** container. An account per user
from a single address is how a single address stops being served, and it
would take the shared relay down with it.

So sessions are pooled rather than granted per person, and the limits are
what make the mode honest:

- At most `WAZE_USER_SESSIONS_MAX` sessions exist at once. Somebody who signs
  in when they are all taken is served by the shared feed, and the response
  says `"session": "shared"` so the app can tell them.
- Accounts are lent out and handed back as sessions retire, never minted per
  person, and the day's minting budget is shared with the shared relay.
- Two sessions cannot share an account, because the upstream login logs the
  other device out. That is what makes the concurrency limit a physical
  limit rather than a tuning knob.

**The honest end state is the phone running its own session**, as sabre-plus
does, with its own address. This mode is the stepping stone, and it is true
for the first few signed-in people at a time rather than for everybody.

```
GET /flare/v1/me/alerts?lat&lon&r
Authorization: Bearer <Firebase ID token>

{"alerts": [...], "ttl_s": 60, "as_of": "...", "session": "user" | "shared"}
```

A separate path from `/flare/v1/alerts` on purpose: the shared endpoint stays
unauthenticated and conformance-clean. The answer comes from that person's
own cache **at once** and never waits on the upstream, because an upstream
query long-polls for up to ten and a half seconds. A refresh runs behind the
answer when their cache is older than twelve seconds or they have moved more
than four kilometres; a jump over twenty-five kilometres throws the old city
away rather than showing it; and a cache nobody could refresh for ten minutes
stops being served. So the first call after signing in returns little and
fills within seconds.

The mode is off unless `WAZE_USER_SESSIONS` is set, and when it is off the
path answers 404 and the handshake says nothing about it. When it is on, the
handshake carries an extension so an app can find it without hardcoding:

```json
"extensions": {"user_sessions": {"path": "/flare/v1/me/alerts",
                                 "auth": "firebase",
                                 "idle_s": 600, "max_concurrent": 5,
                                 "poll_s": 15}}
```

That is a plugin extension, not part of flare/1. Read the numbers rather
than assuming them.

`poll_s`, and the `ttl_s` on the answer, are **not** the handshake's
`refresh_s`. `refresh_s` is the hint for a mediated caller working through a
grid a cell at a time, once a minute. A phone holding its own session is a
different animal: its cache goes stale in twelve seconds and it is moving, so
caching a personal answer for a minute would show a driver where they were a
minute ago. Poll this path at `poll_s`, the protocol floor, not at
`refresh_s`.

### What it knows about you

The token is checked and then almost all of it is thrown away: what is kept
is a keyed hash of the subject, long enough to tell two people apart and
useless for anything else. The token, the account id, the email and the name
are never stored, never logged and never reach the upstream. The hashing key
is generated at boot unless one is configured, so the keys do not outlive a
restart. Positions are rounded to two decimals, about 1.1 km, before they are
used, and the raw value is never logged.

**An app must only ever send a sign-in token to a plugin base it trusts** and
that means one that came from the CommuteScout catalog, never a plugin URL a
user typed in. A plugin is third party by definition, and Flare's own rules
say it must never see a user identity. The cleaner long-term shape is the
backend minting a per-plugin pseudonym, the way `flare.reporter_pseudonym`
already does, and the app sending that instead; this endpoint would take it
with no change to the path or the response.

## Reports and confirmations

**Confirmations** stay here. An `up` or `gone` vote raises the confirmation
count and the confidence this plugin reports, and three `gone` votes hide the
alert. Nothing is sent upstream.

**Reports** are off by default, so `capabilities.report` is `false` and
`/flare/v1/report` answers 404. The client underneath does support
submitting one, the full sequence sabre-plus uses (the tile fetch, the
nearest-segment snap, the position update and the report itself), and
`WAZE_REPORTS=1` turns the endpoint on. It is off on the public deployment
for two reasons: the approved plan says a public listing carries no reports,
and one shared anonymous account writing on behalf of anyone at all is the
fastest way to lose the read path as well. Turn it on for a deployment you
run for yourself.

## Credit and licence

The upstream client is a port of the `waze` package and the Waze half of
`AlertMapper.java` from
[highway-radar-sabre-plus](https://github.com/nicglazkov/highway-radar-sabre-plus),
used under the MIT licence. The port keeps the same endpoints, the same
request and response encoding, the same session handling, and the same
cadence, caching and backoff. `tests/test_waze_client.py` is that project's
own test suite ported case for case.

`AlertDeduper.java` is deliberately not ported: it collapses pins that
different sources report for the same event, and a plugin sees only its own
source. The backend already outranks plugin alerts with agency data on the
same spot.
