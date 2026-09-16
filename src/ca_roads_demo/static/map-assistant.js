// Map page: the assistant (question form, answer card, beacons).
// Split out of map.html on 2026-09-17 with no changes. Classic script on
// purpose: its top-level const/let are shared with map-app.js exactly as
// the two inline blocks shared them.
const form = document.getElementById('form');
const input = document.getElementById('q');
const go = document.getElementById('go');
const answer = document.getElementById('answer');
const statusEl = document.getElementById('status');
const result = document.getElementById('result');
const mapcard = document.getElementById('mapcard');
const loader = document.getElementById('loader');
const loadmsg = document.getElementById('loadmsg');

const KIND_COLORS = {
  incident: '#c9611a',
  lane_closure: '#a02c2c',
  full_closure: '#7f1d1d',
  ramp_closure: '#d9a0a0',
  chain_control: '#2b6cb0',
  wildfire: '#d97706',
  camera: '#1c3a2e',
  sign: '#6b5b1e',
};
// Marker style per closure_class: severity should be readable at a glance.
const CLOSURE_STYLES = {
  'full-roadway':      { radius: 10, fillColor: '#7f1d1d', fillOpacity: 1 },
  'lane':              { radius: 7,  fillColor: '#a02c2c', fillOpacity: 0.95 },
  'one-way-traffic':   { radius: 7,  fillColor: '#a02c2c', fillOpacity: 0.15,
                         color: '#a02c2c', weight: 2.5 },
  'alternating-lanes': { radius: 7,  fillColor: '#a02c2c', fillOpacity: 0.15,
                         color: '#a02c2c', weight: 2.5 },
  'moving':            { radius: 6,  fillColor: '#a02c2c', fillOpacity: 0.15,
                         color: '#a02c2c', weight: 2 },
  'traffic-break':     { radius: 6,  fillColor: '#a02c2c', fillOpacity: 0.15,
                         color: '#a02c2c', weight: 2 },
  'ramp':              { radius: 5,  fillColor: '#d9a0a0', fillOpacity: 0.9 },
  'other':             { radius: 5,  fillColor: '#d9a0a0', fillOpacity: 0.9 },
};
function closureChipKind(cls) {
  if (cls === 'full-roadway') return 'full_closure';
  if (cls === 'ramp' || cls === 'other') return 'ramp_closure';
  return 'lane_closure';
}

// ── Loading animation ────────────────────────────────────────────────
const LOAD_MSGS = [
  'Waking up the dispatcher',
  'Reading the CHP wire',
  'Checking Caltrans closures',
  'Scanning chain controls',
  'Looking for fires near the road',
  'Putting the picture together',
];
const loadtime = document.getElementById('loadtime');
let loadTimer = null, loadIdx = 0, loadStart = 0;
function startLoader() {
  loadIdx = 0;
  loadStart = Date.now();
  loadmsg.textContent = LOAD_MSGS[0];
  loadtime.textContent = 'usually 5 to 15 seconds';
  loader.classList.add('active');
  if (typeof setTool === 'function') setTool('ask', { toggle: false });
  mobileReveal(loader);
  clearInterval(loadTimer);
  loadTimer = setInterval(() => {
    loadIdx = (loadIdx + 1) % LOAD_MSGS.length;
    loadmsg.textContent = LOAD_MSGS[loadIdx];
    const elapsed = (Date.now() - loadStart) / 1000;
    if (elapsed > 30) loadtime.textContent = 'still working, almost there';
    else if (elapsed > 15) loadtime.textContent = 'busy feeds today, can take up to 30 seconds';
  }, 2100);
}
function loaderNote(text) { loadmsg.textContent = text; }
function stopLoader() {
  clearInterval(loadTimer);
  loader.classList.remove('active');
}

// ── Tiny markdown renderer (bold, italics, code, headings, lists) ────
function esc(s) {
  // Escapes quotes too, not just angle brackets: esc() output is used in
  // double-quoted HTML attributes (e.g. data-inc="...") as well as text,
  // and an unescaped " there breaks out of the attribute. renderMd's
  // trailing .replaceAll('"','&quot;') becomes a harmless no-op now.
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function inline(s) {
  return s
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*\s][^*]*)\*/g, '<em>$1</em>');
}
function renderMd(md) {
  // "options" fenced blocks become clarify boxes with clickable choices.
  const optBlocks = [];
  md = md.replace(/```options\n([\s\S]*?)(?:```|$)/g, (_, body) => {
    optBlocks.push(body.trim());
    return '\n@@OPTIONS' + (optBlocks.length - 1) + '@@\n';
  });
  const lines = esc(md).split('\n');
  let html = '', list = null, para = [];
  const flushPara = () => {
    if (para.length) { html += '<p>' + para.map(inline).join('<br>') + '</p>'; para = []; }
  };
  const flushList = () => {
    if (list) {
      html += '<' + list.tag + '>' +
        list.items.map(i => '<li>' + inline(i) + '</li>').join('') +
        '</' + list.tag + '>';
      list = null;
    }
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    const h = line.match(/^#{1,4}\s+(.*)/);
    const ol = line.match(/^\s*\d+[.)]\s+(.*)/);
    const ul = line.match(/^\s*[-*•]\s+(.*)/);
    if (h) { flushPara(); flushList(); html += '<h4>' + inline(h[1]) + '</h4>'; }
    else if (ol) {
      flushPara();
      if (!list || list.tag !== 'ol') { flushList(); list = {tag: 'ol', items: []}; }
      list.items.push(ol[1]);
    } else if (ul) {
      flushPara();
      if (!list || list.tag !== 'ul') { flushList(); list = {tag: 'ul', items: []}; }
      list.items.push(ul[1]);
    } else if (!line.trim()) { flushPara(); flushList(); }
    else { flushList(); para.push(line); }
  }
  flushPara(); flushList();
  html = html.replace(/@@OPTIONS(\d+)@@/g, (_, i) => {
    const rows = (optBlocks[+i] || '').split('\n').filter(l => l.trim());
    if (!rows.length) return '';
    const q = esc(rows[0]);
    const buttons = rows.slice(1).map(o =>
      '<button type="button" class="optbtn" data-opt="' +
      esc(o.trim()).replaceAll('"', '&quot;') + '">' + esc(o.trim()) + '</button>'
    ).join('');
    return '<div class="clarify"><p>' + q + '</p>' + buttons + '</div>';
  });
  return html;
}

// ── Map ──────────────────────────────────────────────────────────────
let map = null;
let layerPrimary = null; // route, incidents, closures, chains: drives zoom
let layerFires = null;   // fires: shown, but never widen the view alone

const chipsEl = document.getElementById('chips');
const KIND_LABELS = {
  incident: ['incident', 'incidents'],
  lane_closure: ['closure', 'closures'],
  full_closure: ['road fully closed', 'roads fully closed'],
  ramp_closure: ['ramp closed', 'ramps closed'],
  chain_control: ['chain control', 'chain controls'],
  wildfire: ['wildfire', 'wildfires'],
  camera: ['live camera', 'live cameras'],
  sign: ['sign message', 'sign messages'],
};
let chipCounts = {};

function renderChips() {
  const entries = Object.entries(chipCounts).filter(([, n]) => n > 0);
  chipsEl.classList.toggle('active', entries.length > 0);
  chipsEl.innerHTML = entries.map(([kind, n]) =>
    `<span class="chip" style="--dot:${KIND_COLORS[kind]}">` +
    `${n} ${KIND_LABELS[kind][n === 1 ? 0 : 1]}</span>`).join('');
}

// Where this TAB last looked. sessionStorage, deliberately: it survives
// a reload and dies with the tab, so reloading keeps the area you moved
// to while a brand new tab still opens on where you are. localStorage
// would get this wrong, because someone who scrolled to Chicago
// yesterday still wants their own commute when they open the map today.
const VIEW_KEY = 'cs.view';

function readSavedView() {
  try {
    const v = JSON.parse(sessionStorage.getItem(VIEW_KEY) || 'null');
    // Validate rather than trust: a stale or hand-edited value must not
    // be able to strand the map off the edge of the world.
    if (Array.isArray(v) && v.length === 3
        && Number.isFinite(v[0]) && Math.abs(v[0]) <= 85
        && Number.isFinite(v[1]) && Math.abs(v[1]) <= 180
        && Number.isFinite(v[2]) && v[2] >= 2 && v[2] <= 17) {
      return [[v[0], v[1]], v[2]];
    }
  } catch (e) { /* private mode, or nothing saved yet */ }
  return null;
}

function saveView() {
  if (!map) return;
  try {
    const c = map.getCenter();
    sessionStorage.setItem(VIEW_KEY, JSON.stringify(
      [+c.lat.toFixed(5), +c.lng.toFixed(5), map.getZoom()]));
  } catch (e) { /* private mode or quota: the view just is not kept */ }
}

function ensureMap() {
  mapcard.classList.add('active');
  if (map) return;
  // No preferCanvas here: the dense layers already share one explicit
  // canvas renderer (canvasR), and adding the map-default canvas on top
  // created a second overlapping canvas that swallowed tap hit-testing
  // on iOS WebKit (dots became unclickable on phones).
  // No location permission needed: the IANA timezone narrows a visitor
  // to a region of the country, which is enough for a friendly first
  // view. Anything unrecognized gets the lower 48.
  const TZ_VIEWS = {
    'America/Los_Angeles': [[37.5, -120.0], 6],
    'America/Phoenix': [[34.2, -111.7], 7],
    'America/Denver': [[39.5, -106.0], 6],
    'America/Boise': [[44.4, -114.6], 6],
    'America/Chicago': [[38.5, -92.5], 5],
    'America/New_York': [[39.8, -77.5], 6],
    'America/Detroit': [[43.0, -84.5], 7],
    'America/Indiana/Indianapolis': [[39.9, -86.3], 7],
    'America/Kentucky/Louisville': [[37.8, -85.7], 7],
    'America/Anchorage': [[61.2, -149.5], 6],
    'Pacific/Honolulu': [[20.9, -157.3], 7],
  };
  // Best signal first: where the visitor last left the map, then the
  // edge's city-level guess from the request IP, then the timezone
  // region, then the lower 48. None of these ask permission.
  let view0 = [[39.3, -97.5], 5];
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
    if (TZ_VIEWS[tz]) view0 = TZ_VIEWS[tz];
  } catch (e) { /* default view */ }
  try {
    const el = document.getElementById('bootgeo');
    if (el) {
      const g = JSON.parse(el.textContent);
      if (typeof g.lat === 'number' && typeof g.lon === 'number') {
        view0 = [[g.lat, g.lon], g.zoom || 10];
      }
    }
  } catch (e) { /* fall through to the timezone view */ }
  // A view this tab was moved to outranks every guess above: the
  // visitor already said where they want to be, and a reload should not
  // argue with them. It cannot outlive the tab (see VIEW_KEY), so a new
  // tab still gets the location-based guess.
  const restored = readSavedView();
  if (restored) view0 = restored;
  map = L.map('map', { scrollWheelZoom: true })
    .setView(view0[0], view0[1]);
  // One coalesced write per gesture, at idle: moveend already fires
  // once per gesture rather than continuously, and deferring keeps a
  // synchronous storage write off the pan/zoom path entirely.
  let viewSaveQueued = false;
  map.on('moveend zoomend', () => {
    if (viewSaveQueued) return;
    viewSaveQueued = true;
    const run = () => { viewSaveQueued = false; saveView(); };
    // requestIdleCallback's second argument is an options object; a
    // number there throws.
    if (window.requestIdleCallback) requestIdleCallback(run, { timeout: 1000 });
    else setTimeout(run, 200);
  });
  // Basemap picker: Leaflet's collapsed layers control in the top-right
  // corner (the sidebar is spoken for). Choice sticks per device via
  // localStorage. crossOrigin makes tile loads CORS requests so the
  // service worker can cache them on-device (Stadia's terms allow
  // client-local caching; server-side caching is prohibited).
  const CS_ATTR = '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>'
    + ' &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a>'
    + ' &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  const CS_STAMEN_ATTR = '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>'
    + ' &copy; <a href="https://stamen.com/">Stamen Design</a>'
    + ' &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a>'
    + ' &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  const CS_BASEMAPS = {
    'Smooth': ['alidade_smooth', CS_ATTR],
    'Bright': ['osm_bright', CS_ATTR],
    'Outdoors': ['outdoors', CS_ATTR],
    'Terrain': ['stamen_terrain', CS_STAMEN_ATTR],
  };
  const baseLayers = {};
  for (const [label, [style, attr]] of Object.entries(CS_BASEMAPS)) {
    baseLayers[label] = L.tileLayer(
      'https://tiles.stadiamaps.com/tiles/' + style + '/{z}/{x}/{y}{r}.png',
      { keepBuffer: 4, maxZoom: 17, crossOrigin: 'anonymous',
        attribution: attr });
  }
  let savedBase = null;
  try { savedBase = localStorage.getItem('cs-basemap'); } catch (e) { /* private mode */ }
  (baseLayers[savedBase] || baseLayers.Smooth).addTo(map);
  L.control.layers(baseLayers, null, { position: 'topright' }).addTo(map);
  map.on('baselayerchange', (ev) => {
    try { localStorage.setItem('cs-basemap', ev.name); } catch (e) { /* private mode */ }
  });
  layerPrimary = L.featureGroup().addTo(map);
  layerFires = L.featureGroup().addTo(map);
}

function resetMap() {
  if (layerPrimary) layerPrimary.clearLayers();
  if (layerFires) layerFires.clearLayers();
  mapcard.classList.remove('active');
  chipCounts = {};
  renderChips();
  document.getElementById('roadinfo').textContent = '';
}

// Road-following geometry comes from Stadia's Valhalla endpoint. The
// browser authenticates by Origin (domain auth), so no key ships here.
const VALHALLA_URL = 'https://api.stadiamaps.com/route/v1';

// Valhalla encodes geometry as a precision-6 polyline.
function decodePolyline6(str) {
  let index = 0, lat = 0, lon = 0;
  const out = [];
  while (index < str.length) {
    for (const which of [0, 1]) {
      let shift = 0, result = 0, byte;
      do {
        byte = str.charCodeAt(index++) - 63;
        result |= (byte & 0x1f) << shift;
        shift += 5;
      } while (byte >= 0x20);
      const delta = (result & 1) ? ~(result >> 1) : (result >> 1);
      if (which === 0) lat += delta; else lon += delta;
    }
    out.push([lat / 1e6, lon / 1e6]);
  }
  return out;
}

async function valhallaRoute(points) {
  const locations = points.map(([lat, lon], i) => ({
    lat, lon,
    type: (i === 0 || i === points.length - 1) ? 'break' : 'through',
  }));
  const res = await fetch(VALHALLA_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ locations, costing: 'auto' }),
    signal: AbortSignal.timeout(6000),
  });
  const data = await res.json();
  if (!data.trip?.legs?.length) return null;
  return {
    latlngs: data.trip.legs.flatMap(l => decodePolyline6(l.shape)),
    distance: data.trip.summary.length * 1000,
    duration: data.trip.summary.time,
  };
}

async function anyRoute(points) {
  try { return await valhallaRoute(points); } catch (e) { return null; }
}

async function roadSnap(geo, fallbackLine) {
  const start = geo.origin || geo.route[0];
  const end = geo.destination || geo.route[geo.route.length - 1];
  // Vias keep the router on our corridor; thin to keep the URL reasonable.
  const inner = geo.route.slice(1, -1);
  const step = Math.max(1, Math.ceil(inner.length / 7));
  const vias = inner.filter((_, i) => i % step === 0);
  try {
    // The corridor-following route AND the unconstrained fastest route;
    // the faster wins unless the corridor route is close - the reported
    // events sit on it.
    const viaRoute = await anyRoute([start, ...vias, end]);
    const direct = await anyRoute([start, end]);
    let road = viaRoute || direct;
    if (viaRoute && direct && viaRoute.duration > direct.duration * 1.15) {
      road = direct;
    }
    if (!road) return;
    layerPrimary.removeLayer(fallbackLine);
    L.polyline(road.latlngs, {
      color: '#1c3a2e', weight: 4, opacity: 0.75,
    }).addTo(layerPrimary);
    const miles = road.distance / 1609.344;
    const mins = road.duration / 60;
    document.getElementById('roadinfo').textContent =
      `~${miles.toFixed(0)} mi by road, ~${mins.toFixed(0)} min without delays`;
  } catch (e) { /* corridor fallback line stays */ }
}

function drawGeo(geo) {
  ensureMap();
  if (geo.user) {
    L.marker(geo.user, {
      icon: L.divIcon({ className: 'youarehere', iconSize: [16, 16] }),
      interactive: false,
      zIndexOffset: 500,
    }).addTo(layerPrimary);
  }
  if (geo.route) {
    const fallbackLine = L.polyline(geo.route, {
      color: '#1c3a2e', weight: 3, opacity: 0.55, dashArray: '6 6',
    }).addTo(layerPrimary);
    roadSnap(geo, fallbackLine);
    const ends = [
      [geo.origin || geo.route[0], 'A', 'Start'],
      [geo.destination || geo.route[geo.route.length - 1], 'B', 'Destination'],
    ];
    for (const [pt, letter, label] of ends) {
      L.marker(pt, {
        icon: L.divIcon({ className: 'route-end', html: letter, iconSize: [22, 22] }),
        zIndexOffset: 400,
      }).bindPopup(label).addTo(layerPrimary);
    }
  }
  for (const m of geo.markers || []) {
    if (m.kind === 'camera') {
      chipCounts.camera = (chipCounts.camera || 0) + 1;
      const camHtml = (typeof popupFor === 'function')
        ? popupFor({ name: m.label, image: m.image, route: '', direction: '',
                     near: '', stream: null }, 'camera')
        : esc(String(m.label || 'camera'));
      L.circleMarker([m.lat, m.lon], {
        radius: 7, color: '#fff', weight: 1.5,
        fillColor: '#2f81f7', fillOpacity: 0.95,
      }).bindPopup(camHtml, { maxWidth: 320 }).addTo(layerPrimary);
      continue;
    }
    if (m.kind === 'wildfire' && Array.isArray(m.poly) && m.poly.length > 0
        && (Array.isArray(m.poly[0] && m.poly[0][0]) || m.poly.length > 2)) {
      chipCounts.wildfire = (chipCounts.wildfire || 0) + 1;
      L.polygon(m.poly, {
        color: '#d97706', weight: 1.5, fillColor: '#d97706', fillOpacity: 0.22,
      // esc(): the label is agency feed text bound as popup HTML. The
      // point-marker path below escapes it; this one must too.
      }).bindPopup(esc(m.label ? String(m.label) : 'wildfire'))
        .addTo(layerFires);
      continue;
    }
    const target = m.kind === 'wildfire' ? layerFires : layerPrimary;
    let style = {
      radius: 7, color: '#fffdf7', weight: 1.5,
      fillColor: KIND_COLORS[m.kind] || '#26261f', fillOpacity: 0.95,
    };
    let chipKind = m.kind;
    if (m.kind === 'lane_closure') {
      chipKind = closureChipKind(m.cls);
      style = Object.assign(
        { color: '#fffdf7', weight: 1.5 },
        CLOSURE_STYLES[m.cls] || CLOSURE_STYLES['lane']
      );
    }
    chipCounts[chipKind] = (chipCounts[chipKind] || 0) + 1;
    let html;
    if (m.kind === 'sign' && typeof popupFor === 'function') {
      html = popupFor(m, 'sign');
    } else {
      const kindLabel = (KIND_LABELS[chipKind] || [m.kind])[0] || m.kind;
      html = '<div class="pop"><div class="k"><i style="--dot:' +
        (KIND_COLORS[m.kind] || '#5b6b7d') + '"></i>' +
        esc(String(kindLabel).toUpperCase()) + '</div><div class="d">' +
        esc(m.label ? String(m.label) : '') + '</div></div>';
    }
    L.circleMarker([m.lat, m.lon], style)
      .bindPopup(html, { maxWidth: 320 }).addTo(target);
  }
  renderChips();
  // Zoom to the road-relevant layer; fall back to fires only when the
  // question was purely about fires.
  const primary = layerPrimary.getBounds();
  const bounds = primary.isValid() ? primary : layerFires.getBounds();
  if (bounds.isValid()) map.fitBounds(bounds.pad(0.18), { maxZoom: 11 });
  setTimeout(() => map.invalidateSize(), 60);
}

// The Ask section's location toggle is gone (it crowded the
// panel); questions carry no coordinates now.
let userLocation = null;

function beacon(event, extra) {
  const payload = JSON.stringify(Object.assign({event}, extra || {}));
  try { navigator.sendBeacon('/api/event', new Blob([payload], {type: 'application/json'})); }
  catch (e) { fetch('/api/event', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: payload}).catch(() => {}); }
}
beacon('pageview');
if ('serviceWorker' in navigator) {
  // Idle-time registration: caches Leaflet/fonts/icons for instant
  // repeat visits; pages and data always come from the network.
  setTimeout(() => navigator.serviceWorker.register('/sw.js')
    .catch(() => {}), 3500);
}

ensureMap();
// The KPI strip first re-polls fast while a fresh server instance is
// still warming its state feeds, so the headline numbers climb to the
// real nationwide totals. After warm-up it keeps refreshing every 30 s,
// the same cadence as the map's ambient refresh below, so a long-lived
// tab (wall monitor / kiosk) shows current counts instead of freezing
// on whatever was true at page load. Hidden tabs skip the fetch and
// the visibility listener catches up the moment the tab is shown.
// /api/stats is rate-limit exempt and served from the feed caches.
let statsTimer = null;
function pollStats(attempt) {
  clearTimeout(statsTimer);
  const later = (ms, next) => {
    statsTimer = setTimeout(() => pollStats(next), ms);
  };
  if (document.visibilityState === 'hidden') { later(30000, attempt); return; }
  fetch('/api/stats').then(r => r.json()).then(s => {
    const put = (id, v) => {
      const el = document.getElementById(id);
      if (el && typeof v === 'number') el.textContent = v.toLocaleString();
    };
    put('k-inc', s.incidents); put('k-clo', s.closures);
    put('k-cc', s.chain_controls); put('k-wf', s.wildfires);
    put('k-cam', s.cameras); put('k-st', s.states);
    if (s.sources && s.states) {
      document.getElementById('feedsok').textContent =
        'live from ' + s.sources + ' sources in ' + s.states + ' states' +
        (s.warm_total && s.warm_ready < s.warm_total
          ? ', warming ' + s.warm_ready + '/' + s.warm_total : '');
    }
    const warming = s.warm_total && s.warm_ready < s.warm_total;
    if (warming && attempt < 40) later(8000, attempt + 1);
    else later(30000, 40);
  }).catch(() => later(30000, attempt));
}
pollStats(0);
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') pollStats(40);
});

fetch('/health').then(r => r.json()).then(d => {
  if (d.version) document.getElementById('ver').textContent = ' v' + d.version;
}).catch(() => {});

document.querySelectorAll('.examples button').forEach(b => {
  b.addEventListener('click', () => {
    beacon('example_click');
    input.value = b.textContent; form.requestSubmit();
  });
});

const morebtn = document.getElementById('morebtn');
let lastQuestion = '', lastAnswerRaw = '';

async function runQuery(question, prior) {
  go.disabled = true;
  morebtn.classList.remove('active');
  morebtn.disabled = true;
  document.getElementById('feedback').classList.remove('active');
  result.classList.add('active');
  let target = answer;
  if (prior) {
    // Follow-up detail streams under a divider; the map keeps building.
    const rule = document.createElement('hr');
    rule.className = 'more-rule';
    const heading = document.createElement('p');
    heading.className = 'more-heading';
    heading.textContent = 'The full picture';
    const section = document.createElement('div');
    answer.append(rule, heading, section);
    target = section;
  } else {
    answer.innerHTML = '';
    resetMap();
  }
  startLoader();
  let raw = '';
  try {
    const payload = {question, tz: Intl.DateTimeFormat().resolvedOptions().timeZone};
    if (userLocation) payload.location = userLocation;
    if (prior) payload.prior = prior;
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      stopLoader();
      target.textContent = err.error || `Request failed (${res.status}).`;
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});
      const parts = buffer.split('\n\n');
      buffer = parts.pop();
      for (const part of parts) {
        if (!part.startsWith('data: ')) continue;
        const msg = JSON.parse(part.slice(6));
        if (msg.text) {
          raw += msg.text;
          target.innerHTML = renderMd(raw);
          statusEl.textContent = '';
          stopLoader();
        }
        if (msg.tool) {
          const label = 'Looking up ' + msg.tool.replaceAll('_', ' ');
          if (loader.classList.contains('active')) loaderNote(label);
          else statusEl.textContent = label + '…';
        }
        if (msg.map) { drawGeo(msg.map); }
        if (msg.done) { statusEl.textContent = ''; }
      }
    }
    if (!prior) {
      lastQuestion = question;
      lastAnswerRaw = raw;
      // Offer depth when there's clearly more behind the summary.
      const totalEvents = Object.values(chipCounts).reduce((a, b) => a + b, 0);
      if (totalEvents >= 4 || raw.length > 900) {
        morebtn.disabled = false;
        morebtn.classList.add('active');
      }
      feedbackEl.innerHTML = '<span>Was this right?</span>' +
        '<button type="button" data-fb="feedback_up" aria-label="Yes">&#128077;</button>' +
        '<button type="button" data-fb="feedback_down" aria-label="No">&#128078;</button>';
      feedbackEl.querySelectorAll('button').forEach(b => {
        b.addEventListener('click', () => {
          beacon(b.dataset.fb, {question: lastQuestion});
          feedbackEl.innerHTML = '<span class="thanks">Thanks, noted.</span>';
        });
      });
      feedbackEl.classList.add('active');
    }
  } catch (err) {
    statusEl.textContent = 'Connection error. Try again.';
  } finally {
    stopLoader();
    go.disabled = false;
    statusEl.textContent = '';
  }
}

form.addEventListener('submit', (e) => {
  e.preventDefault();
  const question = input.value.trim();
  if (question) runQuery(question, null);
});

const feedbackEl = document.getElementById('feedback');
feedbackEl.querySelectorAll('button').forEach(b => {
  b.addEventListener('click', () => {
    beacon(b.dataset.fb, {question: lastQuestion});
    feedbackEl.innerHTML = '<span class="thanks">Thanks, noted.</span>';
  });
});

answer.addEventListener('click', (e) => {
  const btn = e.target.closest('.optbtn');
  if (!btn) return;
  input.value = lastQuestion + ' (I mean ' + btn.dataset.opt + ')';
  form.requestSubmit();
});

morebtn.addEventListener('click', () => {
  if (!lastQuestion || !lastAnswerRaw) return;
  beacon('tell_more');
  runQuery(
    'Tell me more. Go through everything you found in detail.',
    {question: lastQuestion, answer: lastAnswerRaw}
  );
});
