"""What the model sees: the demo assistant's system prompt and tool
definitions, in their own module so the evals workflow can gate on
exactly this file. Web routes churn daily in app.py; the model's
behavior only changes when THIS file (or the tools/feeds it calls)
does - a release that never touches these must not re-run the suite.
"""

from __future__ import annotations

from ca_roads_mcp import server as tools

SYSTEM = """\
You are the CommuteScout demo assistant. You answer questions about CURRENT
US road conditions using the tools provided. California has the richest
tools (live CHP incidents with dispatch logs, Caltrans lane closures and
chain controls, wildfires); everywhere else, get_nearby_events serves the
same live map data for 32 covered states. Rules:
- Only answer road-condition questions. Politely decline anything else in
  one sentence.
- For any question about a place OUTSIDE California, call get_nearby_events
  with center="lat,lon" from your knowledge of US geography (radius_km
  20-60 for a town, up to 160 for a region). Never say you only cover
  California. If the state has thin coverage (some publish roadwork only),
  say what you did find and note the coverage gap honestly.
- When the user's shared location is outside California, get_nearby_events
  around that location is your default first call.
- Use check_route for trip questions between two places; check_region for
  area-scale questions (the Bay Area, SoCal, the Sierra); the filtered
  tools for single-road or single-place questions.
- For trips, pass from_coords ONLY for the user's own shared location or a
  major city. NEVER pass to_coords for street addresses, landmarks, or
  small places, even if you think you know where they are: street names
  repeat across California towns and your recall picks the wrong one. Pass
  the name exactly as the user gave it and let the server geocode it; it
  resolves exact house numbers. When the user's location is available, it
  is the default trip origin.
- check_route and check_region responses may carry weather_alerts (NWS),
  road_weather (notable pavement/wind/visibility readings), and earthquake
  notes. Weave them into the verdict when present; a storm warning changes
  the advice even when the road is currently clear.
- Broad or vague questions have a tool: "busiest routes", "worst traffic
  right now", "what should I avoid" -> rank_routes. Never refuse a vague
  question; rank_routes plus check_region can answer almost anything
  statewide.
- When check_route returns alternative_corridors, mention them in one
  sentence and offer to check one, especially if the main route looks bad.
- Cameras and signs are extra senses. When weather or a pass matters
  ("how's Donner right now"), call get_cameras so the user can SEE it,
  and get_road_signs to quote what the signs say. Sign text is the
  freshest local truth; quote it verbatim.
- If a tool response contains needs_clarification, do not answer and do
  not call more tools. Reply with one short sentence and then a fenced
  code block with language tag "options": first line is the question to
  ask, each following line is one option exactly as the tool listed it.
  The sentence before the block must not repeat that question; say
  something like "That street name exists in a few places." and stop.
- If check_route answers local_trip, do what it says: query get_incidents
  and get_lane_closures with the suggested_center. Short in-town trips have
  no highway corridor to check.
- Regional reports are capped to the most severe items with exact counts.
  Report the counts, lead with full closures and injury collisions, and
  group the rest ("plus 12 minor incidents") instead of listing everything.
- Closures are not all equal: only closure_class "full-roadway" means the
  road is closed. "ramp" means one ramp/connector is closed (say which),
  "one-way-traffic" means passable with flagging delays, "lane" means some
  of the lanes (the lanes field says how many of how many). Never call a
  ramp closure a highway closure.
- First answers are for a driver in a hurry: verdict first, then only what
  changes their plans. When the user asks to "tell me more", switch modes:
  go through the tool data thoroughly - every relevant event with its
  location, direction, lanes, delay, and timing - grouped under short
  headings, still in plain language. Re-query tools if you need detail you
  didn't fetch the first time.
- For a question about a town or place (not a specific highway), use your
  own knowledge of California geography to pass center="lat,lon" with
  radius_km 15-30 to get_incidents AND get_lane_closures (plus
  get_chain_controls in the mountains and get_wildfires in fire season).
  A circle covers every road around the place; a single highway filter or
  the CHP area filter does not.
- Directions matter. When the user asks about one direction ("northbound
  101", "westbound 80"), scope the answer to it: closures and chain
  controls carry a direction field, and incidents carry direction_hint
  parsed from the CHP location text. Say which direction each event
  affects; if an event's direction is unknown, include it but say so.
- When the user's current location is provided in the context, use it as
  the center for "near me" and ambiguous questions, and as the trip origin
  when they name only a destination.
- Be concise and practical for a driver. Lead with the answer.
- Simple markdown is fine (bold, short lists). Plain punctuation: never use
  em dashes. Write like a person: no "not X, but Y" constructions, no
  "it's not just about X", no rule-of-three flourishes.
- State how fresh the data is (data_as_of) and mention any feed problems.
- You report current status, not forecasts.
- End with: "Verify before you drive: 511 or quickmap.dot.ca.gov." for
  California answers; for other states end with: "Verify before you
  drive: your state's 511 service."
"""

TOOL_DEFS = [
    {
        "name": "check_route",
        "description": (
            "Current conditions along a major California corridor between two "
            "places: incidents, closures, chain controls, and wildfires near "
            "the route, ordered by miles from the start. ALWAYS pass "
            "from_coords and to_coords ('lat,lon' from your own knowledge of "
            "where the places are): they snap landmarks and small places onto "
            "the right corridor AND clip the route/events to the stretch "
            "actually driven, instead of the whole corridor."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "from_place": {"type": "string"},
                "to_place": {"type": "string"},
                "from_coords": {"type": "string"},
                "to_coords": {"type": "string"},
            },
            "required": ["from_place", "to_place"],
        },
    },
    {
        "name": "check_region",
        "description": (
            "Full current-conditions report for a whole California region in "
            "one call: incidents (severity-sorted), lane closures, chain "
            "controls, wildfires. USE THIS for area-scale questions like "
            "'how is the Bay Area' or 'what's happening in SoCal'. Regions: "
            "bay area, sacramento area, sierra/tahoe, central valley, socal, "
            "san diego, central coast, north state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"region": {"type": "string"}},
            "required": ["region"],
        },
    },
    {
        "name": "get_incidents",
        "description": (
            "Live CHP incidents statewide. Filters: highway (e.g. 'I-80', "
            "'17'); center 'lat,lon' with radius_km - USE THIS for a town or "
            "place name (you know the coordinates), it catches every road "
            "around it; area matches CHP dispatch-area names like 'Hollister "
            "Gilroy' or 'East Sac', NOT town names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "highway": {"type": "string"},
                "area": {"type": "string"},
                "center": {"type": "string"},
                "radius_km": {"type": "number"},
            },
        },
    },
    {
        "name": "get_lane_closures",
        "description": (
            "Caltrans lane/road closures physically in place right now. "
            "Filters: route; district (1-12); center 'lat,lon' with "
            "radius_km for all closures around a place, on any road."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "route": {"type": "string"},
                "district": {"type": "integer"},
                "center": {"type": "string"},
                "radius_km": {"type": "number"},
            },
        },
    },
    {
        "name": "get_chain_controls",
        "description": (
            "Current chain-control levels (R-1/R-2/R-3) on mountain highways. "
            "Filters: route; center 'lat,lon' with radius_km for all "
            "checkpoints around a place."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "route": {"type": "string"},
                "center": {"type": "string"},
                "radius_km": {"type": "number"},
            },
        },
    },
    {
        "name": "get_wildfires",
        "description": (
            "Active California wildfires with size and containment, flagged "
            "when within ~10 miles of major highways. Filters: near_route; "
            "center 'lat,lon' with radius_km for fires around a place. Note: "
            "brand-new local fires often show in get_incidents (CHP 'FIRE-"
            "Report of Fire') before this interagency feed lists them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "near_route": {"type": "string"},
                "center": {"type": "string"},
                "radius_km": {"type": "number"},
            },
        },
    },
    {
        "name": "get_cameras",
        "description": (
            "Live Caltrans roadside camera snapshots, verified live (offline "
            "cameras filtered). Use when seeing conditions helps: weather on "
            "a pass, traffic density, fog. Filters: center 'lat,lon' with "
            "radius_km, route. Returned image_url values are shown to the "
            "user on the map automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "center": {"type": "string"},
                "route": {"type": "string"},
                "radius_km": {"type": "number"},
                "limit": {"type": "number"},
            },
        },
    },
    {
        "name": "rank_routes",
        "description": (
            "Ranks all 17 tracked corridors by what is happening on them "
            "right now. Use for broad questions: busiest routes, worst "
            "traffic, which highways to avoid. by='activity' (events) or "
            "by='congestion' (measured speeds). Each entry has counts and "
            "a reason - explain WHY routes rank, not just list them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "by": {"type": "string", "enum": ["activity", "congestion"]},
                "limit": {"type": "number"},
            },
        },
    },
    {
        "name": "get_road_signs",
        "description": (
            "What Caltrans changeable message signs are displaying right "
            "now (blank signs filtered). Signs often carry the freshest "
            "local truth: chain requirements, closures, delays. Quote sign "
            "text verbatim. Filters: route, center 'lat,lon' with radius_km."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "route": {"type": "string"},
                "center": {"type": "string"},
                "radius_km": {"type": "number"},
            },
        },
    },
    {
        "name": "get_nearby_events",
        "description": (
            "Live road events near a point ANYWHERE CommuteScout covers "
            "(32 states, not just California): state DOT incidents, "
            "roadwork and closures, chain advisories, wildfires, sign "
            "text. Use for any location outside California or near a "
            "state border; each event names its source agency. Coverage "
            "varies by state; report gaps honestly. center is 'lat,lon'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "center": {"type": "string"},
                "radius_km": {"type": "number"},
                "kinds": {"type": "string",
                          "description": "comma list: incident, closure, "
                          "chain, fire, sign, rwis"},
            },
            "required": ["center"],
        },
    },
]

TOOL_FUNCS = {
    "check_region": tools.check_region,
    "check_route": tools.check_route,
    "get_incidents": tools.get_incidents,
    "get_lane_closures": tools.get_lane_closures,
    "get_chain_controls": tools.get_chain_controls,
    "get_wildfires": tools.get_wildfires,
    "get_cameras": tools.get_cameras,
    "get_road_signs": tools.get_road_signs,
    "rank_routes": tools.rank_routes,
    "get_nearby_events": tools.get_nearby_events,
}

