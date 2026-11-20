// Snapshot of /api/flare/sources (the live plugin catalog), taken 2026-11-20 00:35 UTC
// for this local-only lab board. The real page reads the endpoint live.

export type Plugin = {
  id: string;
  name: string;
  attribution: { name: string; url: string };
  trust: string;
  tier: "approved" | "unreviewed";
  visibility: string;
  count: number;
  stale: boolean;
  ok: boolean;
  last_ok: string;
  version: string;
  protocol: string;
  refresh_s: number;
  contact: string;
  description: string;
  coverage: number[];
  kinds: string[];
  capabilities: Record<string, boolean>;
  shared: boolean;
};

export const PLUGINS: Plugin[] = [
  {
    "id": "osm-cameras",
    "name": "Speed and red light cameras",
    "attribution": {
      "name": "OpenStreetMap contributors and city open data",
      "url": "https://github.com/nicglazkov/commutescout-plugins/tree/main/osm-cameras"
    },
    "trust": "official",
    "tier": "approved",
    "visibility": "public",
    "count": 2320,
    "stale": true,
    "ok": true,
    "last_ok": "2026-11-19T23:55:51.989184+00:00",
    "version": "1.1.0",
    "protocol": "flare/1",
    "refresh_s": 3600,
    "contact": "mailto:hello@commutescout.com",
    "description": "Fixed speed and red light cameras from OpenStreetMap and from cities that publish their own lists (Chicago, Washington DC, San Francisco). Complete in those cities; elsewhere, whatever has been mapped.",
    "coverage": [
      18.0,
      -168.0,
      71.5,
      -66.5
    ],
    "kinds": [
      "CAMERA_RED_LIGHT",
      "CAMERA_SPEED"
    ],
    "capabilities": {
      "alerts": true,
      "report": false,
      "confirm": false,
      "notify": false,
      "snapshot": true
    },
    "shared": true
  },
  {
    "id": "wz-flare",
    "name": "Unofficial Waze relay (community)",
    "attribution": {
      "name": "Unofficial Waze relay (community)",
      "url": "https://commutescout.com/plugins"
    },
    "trust": "community",
    "tier": "unreviewed",
    "visibility": "public",
    "count": 89,
    "stale": false,
    "ok": true,
    "last_ok": "2026-11-20T00:34:47.745508+00:00",
    "version": "1.3.0",
    "protocol": "flare/1",
    "refresh_s": 60,
    "contact": "https://commutescout.com/contact",
    "description": "Crowd reports from Waze: police, crashes, hazards, jams. Unofficial, at your own risk.",
    "coverage": [
      18.0,
      -168.0,
      71.5,
      -66.5
    ],
    "kinds": [
      "CAMERA_SPEED",
      "CRASH_MAJOR",
      "CRASH_MINOR",
      "HAZARD_ANIMAL",
      "HAZARD_CONSTRUCTION",
      "HAZARD_OBJECT",
      "HAZARD_ON_ROAD",
      "HAZARD_POTHOLE",
      "HAZARD_SHOULDER",
      "HAZARD_SHOULDER_ANIMAL",
      "HAZARD_SHOULDER_CAR",
      "JAM_HEAVY",
      "JAM_MODERATE",
      "JAM_STANDSTILL",
      "LANE_CLOSED",
      "OTHER",
      "POLICE_HIDING",
      "POLICE_VISIBLE",
      "ROAD_CLOSED",
      "WEATHER_FLOOD",
      "WEATHER_FOG",
      "WEATHER_HAIL",
      "WEATHER_ICE",
      "WEATHER_SNOW"
    ],
    "capabilities": {
      "alerts": true,
      "report": false,
      "confirm": true,
      "notify": false
    },
    "shared": false
  }
];
