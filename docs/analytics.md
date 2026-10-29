# Querying the event archive

Every incident, closure, chain control, and wildfire in all 37 covered
states is archived to BigQuery as append-only lifecycle rows: `appear` when an
event first shows up (full state in `payload`), `update` when something
changes (only the new dispatch entries or changed fields), `clear` when
it leaves the feed. Recording started 2026-07-12 with California; each
other state's events start from the day its feed joined the map.
Dispatch-timeline payloads exist from 2026-07-18 (v2.25.0) onward.

Console: <https://console.cloud.google.com/bigquery?project=ca-roads-mcp>,
table `ca-roads-mcp.events.event_log`. The table is a few MB, far below
the free query tier, so explore freely. For point-and-click dashboards,
connect the table to Looker Studio (BigQuery connector, free).

Two reading rules:

- Instance restarts duplicate `appear` rows by design; dedupe with
  `MIN(first_seen) ... GROUP BY event_id` when counting.
- `payload` is a JSON string: `details` and `units` are lists of
  `[chp_time_string, text]` pairs, scalars live under `state`.

## Daily volume by kind

```sql
SELECT DATE(first_seen) AS day, kind, COUNT(DISTINCT event_id) AS events
FROM `ca-roads-mcp.events.event_log`
WHERE phase = 'appear'
GROUP BY day, kind
ORDER BY day DESC, events DESC;
```

## How long do things last?

```sql
SELECT kind,
       APPROX_QUANTILES(TIMESTAMP_DIFF(seen_at, first_seen, MINUTE), 4) AS quartiles_min
FROM `ca-roads-mcp.events.event_log`
WHERE phase = 'clear' AND TIMESTAMP_DIFF(seen_at, first_seen, MINUTE) > 0
GROUP BY kind;
```

## Busiest hours (Pacific time)

```sql
SELECT EXTRACT(HOUR FROM seen_at AT TIME ZONE 'America/Los_Angeles') AS hour,
       COUNT(DISTINCT event_id) AS new_incidents
FROM `ca-roads-mcp.events.event_log`
WHERE phase = 'appear' AND kind = 'incident'
GROUP BY hour ORDER BY hour;
```

## The vehicle-make leaderboard

CHP dispatchers use shorthand makes (TOYT, HOND, CHEV...). Payload rows
carry the shorthand verbatim, so "how many Toyotas this week" is a scan:

```sql
WITH makes AS (
  SELECT * FROM UNNEST([
    STRUCT('Toyota' AS make, r'\bTOYT\b' AS pat),
    ('Honda', r'\bHOND\b'), ('Ford', r'\bFORD\b'),
    ('Chevrolet', r'\bCHEV\b'), ('Nissan', r'\bNISS\b'),
    ('Tesla', r'\bTESL\b'), ('Dodge', r'\bDODG\b'),
    ('Subaru', r'\bSUBA\b'), ('Hyundai', r'\bHYUN\b'),
    ('Kia', r'\bKIA\b'), ('Jeep', r'\bJEEP\b'), ('BMW', r'\bBMW\b'),
    ('Semi / big rig', r'\bSEMI\b|\bBIG RIG\b')
  ])
)
SELECT DATE_TRUNC(DATE(e.seen_at), WEEK) AS week, m.make,
       COUNT(DISTINCT e.event_id) AS incidents
FROM `ca-roads-mcp.events.event_log` e
CROSS JOIN makes m
WHERE e.kind = 'incident' AND e.payload IS NOT NULL
  AND REGEXP_CONTAINS(e.payload, m.pat)
GROUP BY week, m.make
ORDER BY week DESC, incidents DESC;
```

## Read one incident's full dispatch log

```sql
SELECT e.seen_at, e.phase,
       JSON_VALUE(d, '$[0]') AS chp_time,
       JSON_VALUE(d, '$[1]') AS entry
FROM `ca-roads-mcp.events.event_log` e,
     UNNEST(JSON_QUERY_ARRAY(e.payload, '$.details')) AS d
WHERE e.event_id = 'chp:260718GG0075'   -- any chp:<id>
ORDER BY e.seen_at;
```

## Fire growth over time

```sql
SELECT event_id, seen_at,
       CAST(JSON_VALUE(payload, '$.state.acres') AS FLOAT64) AS acres,
       CAST(JSON_VALUE(payload, '$.state.contained_pct') AS FLOAT64) AS contained_pct
FROM `ca-roads-mcp.events.event_log`
WHERE kind = 'fire' AND payload IS NOT NULL
ORDER BY event_id, seen_at;
```

## Incident hotspots (heatmap grid)

```sql
SELECT ROUND(lat, 2) AS lat, ROUND(lon, 2) AS lon,
       COUNT(DISTINCT event_id) AS incidents
FROM `ca-roads-mcp.events.event_log`
WHERE phase = 'appear' AND kind = 'incident' AND lat IS NOT NULL
GROUP BY lat, lon
HAVING incidents >= 3
ORDER BY incidents DESC;
```

## Severe stuff only (fatalities and SIG alerts)

```sql
SELECT DATE(first_seen) AS day, title, detail, event_id
FROM `ca-roads-mcp.events.event_log`
WHERE phase = 'appear'
  AND REGEXP_CONTAINS(UPPER(title), r'1144|SIG')
ORDER BY day DESC;
```

## Everything near a point (example: South Lake Tahoe, ~20 km box)

```sql
SELECT seen_at, kind, phase, title, detail
FROM `ca-roads-mcp.events.event_log`
WHERE lat BETWEEN 38.75 AND 39.10 AND lon BETWEEN -120.15 AND -119.80
ORDER BY seen_at DESC
LIMIT 100;
```
