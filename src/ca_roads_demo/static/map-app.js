// Map page: the standalone map (layers, popups, planner, tolls, refresh).
// Split out of map.html on 2026-09-17 with no changes. Depends on the
// globals map-assistant.js declares; load order is fixed in map.html.
// ── Standalone map: everything visible, no AI required ──────────────
const canvasR = L.canvas({ padding: 0.4 });
const GROUP_DOT = {
  inc_collision: '#c9611a', inc_fire: '#c9611a', inc_hazard: '#c9611a',
  inc_other: '#c9611a', clo_full: '#7f1d1d', clo_lane: '#a02c2c',
  clo_oneway: '#a02c2c', clo_ramp: '#d9a0a0', chain: '#2b6cb0',
  rwis: '#2f9e6e', fire_pt: '#d97706', fire_poly: '#d97706',
  toll: '#7c3aed', plugin: '#0e9f9f',
  camera: '#2f81f7', sign: '#a16207',
};
const POP_LABEL = {
  inc_collision: 'COLLISION', inc_fire: 'FIRE REPORT', inc_hazard: 'HAZARD',
  inc_other: 'INCIDENT', clo_full: 'FULL CLOSURE', clo_lane: 'LANE CLOSURE',
  clo_oneway: 'ONE-WAY / ROLLING WORK', clo_ramp: 'RAMP CLOSED',
  chain: 'CHAIN CONTROL', rwis: 'ROAD WEATHER', fire_pt: 'WILDFIRE',
  toll: 'TOLL PRICE', plugin: 'COMMUNITY REPORT',
  fire_poly: 'BURN FOOTPRINT', camera: 'LIVE CAMERA', sign: 'MESSAGE SIGN',
};
// Lists (Live near you, the Live tool, the route strip) mark each row
// with its kind: a soft square in the kind's colour with a drawn icon,
// so a crash and a closure differ by shape as well as colour.
const KIND_OF = (g) => g.startsWith('inc_') ? 'incident' : g.startsWith('clo_') ? 'closure'
  : g === 'chain' ? 'chain' : (g === 'fire_pt' || g === 'fire_poly') ? 'fire'
  : g === 'rwis' ? 'weather' : g === 'camera' ? 'camera' : g === 'plugin' ? 'plugin' : 'sign';
const KIND_SVG = {
  incident: '<path d="M12 4 3 19.5h18z"/><path d="M12 10v4.5M12 17v.01"/>',
  closure: '<circle cx="12" cy="12" r="8"/><path d="m6.4 6.4 11.2 11.2"/>',
  chain: '<path d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9"/><path d="m9.5 4.5 2.5 2 2.5-2M9.5 19.5l2.5-2 2.5 2"/>',
  fire: '<path d="M12 21c-3.6 0-6-2.4-6-5.6 0-3.6 3.2-5.4 3.2-9.4 2.6 1.4 4.4 3.6 4.6 6.2.9-.6 1.5-1.8 1.6-3 1.6 1.6 2.6 3.8 2.6 6.2 0 3.2-2.4 5.6-6 5.6z"/>',
  weather: '<path d="M7 15.5a4 4 0 0 1 .5-8 5.5 5.5 0 0 1 10.4 1.6A3.3 3.3 0 0 1 17.5 15.5z"/><path d="M8 19l-.8 1.6M12 19l-.8 1.6M16 19l-.8 1.6"/>',
  camera: '<rect x="3" y="7" width="13" height="10" rx="2"/><path d="m16 11 5-3v8l-5-3"/>',
  sign: '<path d="M12 3v18M7 21h10"/><path d="M5 6h12l2.5 2.5L17 11H5z"/>',
  plugin: '<path d="M12 21s-6.5-5.8-6.5-11a6.5 6.5 0 0 1 13 0c0 5.2-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.2"/>',
};
function kindIcon(g, extra) {
  const k = KIND_OF(g);
  return '<span class="kicon k-' + k + (extra ? ' ' + extra : '') + '" aria-hidden="true">' +
    '<svg viewBox="0 0 24 24">' + KIND_SVG[k] + '</svg></span>';
}
const ambient = {};
Object.keys(GROUP_DOT).forEach(g => {
  ambient[g] = L.layerGroup();
  // The checkbox is the single source of truth from boot onward. A
  // group blindly added while its box was unchecked leaked toll
  // corridor lines onto the map (GL gates dots by checkbox, but
  // Leaflet line layers render the moment their group is on the map).
  const box = document.querySelector('input[data-group="' + g + '"]');
  if (!box || box.checked) ambient[g].addTo(map);
});
let cameraCache = [];
let signCache = [];

function classify(m) {
  if (m.kind === 'incident') {
    const t = (m.type || '').toLowerCase();
    if (/collision|crash|hit and run|hit & run/.test(t)) return 'inc_collision';
    if (/fire/.test(t)) return 'inc_fire';
    if (/hazard|debris|animal|object|ped|road rage/.test(t)) return 'inc_hazard';
    return 'inc_other';
  }
  if (m.kind === 'lane_closure') {
    if (m.cls === 'full-roadway') return 'clo_full';
    if (m.cls === 'ramp') return 'clo_ramp';
    if (/one-way|alternating|moving|traffic-break/.test(m.cls || '')) return 'clo_oneway';
    return 'clo_lane';
  }
  if (m.kind === 'chain_control') return 'chain';
  if (m.kind === 'rwis') return 'rwis';
  if (m.kind === 'toll') return 'toll';
  if (m.kind === 'wildfire') return 'fire_pt';
  if (m.kind === 'camera') return 'camera';
  if (m.kind === 'sign') return 'sign';
  if (m.kind === 'plugin') return 'plugin';
  return null;
}

function popHead(group, title) {
  return '<div class="pop"><div class="k"><i style="--dot:' + GROUP_DOT[group] +
    '"></i>' + POP_LABEL[group] + '</div><div class="t">' + esc(title) + '</div>';
}
// CHP dispatch codes, decoded for people who don't speak scanner.
// Copy spec: warnings lead with the hazard noun, "can" for
// possibility (never "may"), reported-frame preserved, max 3
// sentences per string.
const CHP_CODES = [
  [/^1125/, 'A traffic hazard is on or near the road: debris, an animal, or a stalled vehicle. These usually clear quickly. Expect brief slowing.'],
  [/^1179/, 'Collision with injuries. An ambulance is on the way. Lanes can be blocked while crews work.'],
  [/^1181/, 'Collision with minor injuries reported. Expect brief lane blockage while crews clear the scene.'],
  [/^1182/, 'Collision, property damage only. No injuries are reported. Vehicles can be on the shoulder.'],
  [/^1183/, 'Collision reported, details still coming in. CHP has the call but no injury assessment yet.'],
  [/^20001/, 'Hit and run with injuries (felony). CHP is investigating. The scene can block lanes.'],
  [/^20002/, 'Hit and run, property damage only. Usually a short stop on the shoulder.'],
  [/^23114/, 'A load has spilled from a vehicle onto the road. Lanes can close briefly for cleanup.'],
  [/^1166/, 'A traffic signal is defective. Treat the intersection as an all-way stop.'],
  [/SIG/i, 'A SIG Alert: a major incident expected to block lanes for 30 minutes or more. Avoid the area if you can.'],
  [/fire/i, 'A fire reported on or near the road. Smoke can cut visibility. Expect crews and closures.'],
  [/ped/i, 'A pedestrian is involved or on the road. Slow down and give the scene room.'],
  [/animal/i, 'A live or struck animal on the road. Expect brief slowing.'],
];
function chpGloss(type) {
  for (const [re, text] of CHP_CODES) {
    if (re.test(type || '')) return text;
  }
  return null;
}
// Dispatch-log shorthand, decoded deterministically (no AI): only terms
// we are confident about get translated; everything else stays verbatim.
// Order matters: multi-word phrases first, then hyphenated codes and
// unit callsigns, then bare codes (with lookarounds so codes embedded
// in hyphenated labels or route numbers stay put), then word tokens.
// Built from repeated sweeps of live logs (30 logs per pass).
const CHP_TERMS = [
  // Multi-word phrases before their component tokens.
  [/\bNEG 180\b/g, 'no major injuries'],
  [/\bNEG 144\b/g, 'no fatalities'],
  [/\bCODE 4\b/g, 'no further help needed'],
  [/\bCODE 3\b/g, 'running lights and siren'],
  [/\bVERBAL 415\b/g, 'verbal dispute'],
  [/\bSOLO VEH\b/g, 'single vehicle'],
  [/\bO\/TURNED\b/g, 'overturned'],
  [/\bI\/S\b/g, 'intersection'],
  // Hyphenated 11-code variants radio chatter uses. These MUST run
  // before the callsign rule, which would read "11-10" as a unit.
  [/\b11-10\b/g, 'take a report'],
  [/\b11-24\b/g, 'abandoned vehicle'],
  [/\b11-25\b/g, 'traffic hazard'],
  [/\b11-41\b/g, 'ambulance requested'],
  [/\b11-44\b/g, 'fatality'],
  [/\b11-79\b/g, 'collision, ambulance en route'],
  [/\b11-80\b/g, 'collision with major injuries'],
  [/\b11-81\b/g, 'collision with minor injuries'],
  [/\b11-82\b/g, 'collision, property damage only'],
  [/\b11-83\b/g, 'collision, injuries unknown'],
  [/\b11-85\b/g, 'tow truck requested'],
  [/\b11-98\b/g, 'meet the officer'],
  // Unit callsigns (A62-505 / 612-108 / 18-R1 shapes). The (?!-) tail
  // keeps phone numbers out: their next segment starts with a hyphen.
  [/\b([A-Z]\d{2,3}-\d{2,4}[A-Z]?|\d{2,3}-R?\d{1,3}[A-Z]?)\b(?!-)/g,
   'unit $1'],
  // Bare codes. Lookarounds keep codes inside hyphenated official
  // labels ("1179-Trfc Collision-1141 Enrt") and route numbers
  // (SR-180) verbatim.
  [/(?<![-\d])1185R(?![-\d])/g, 'rotation tow requested'],
  [/(?<![-\d])1185S(?![-\d])/g, 'tow trucks'],
  [/(?<![-\d])1185(?![-\dA-Z])/g, 'tow truck'],
  [/(?<![-\d])1186(?![-\d])/g, 'operator alerted'],
  [/(?<![-\d])1179(?![-\d])/g, 'collision, ambulance en route'],
  [/(?<![-\d])1180(?![-\d])/g, 'collision with major injuries'],
  [/(?<![-\d])1181(?![-\d])/g, 'collision with minor injuries'],
  [/(?<![-\d])1182(?![-\d])/g, 'collision, property damage only'],
  [/(?<![-\d])1183(?![-\d])/g, 'collision, injuries unknown'],
  [/(?<![-\d])1141(?![-\d])/g, 'ambulance requested'],
  [/(?<![-\d])1144(?![-\d])/g, 'fatal collision'],
  [/(?<![-\d])1124(?![-\d])/g, 'abandoned vehicle'],
  [/(?<![-\d])1125A(?![-\d])/g, 'animal on the road'],
  [/(?<![-\d])1125(?![-\dA])/g, 'traffic hazard'],
  [/(?<![-\d])1166(?![-\d])/g, 'defective signal'],
  [/(?<![-\d])1097(?![-\d])/g, 'unit on scene'],
  [/(?<![-\d])1098(?![-\d])/g, 'assignment complete'],
  [/(?<![-\d])1022(?![-\d])/g, 'disregard'],
  [/(?<![-\d])1023(?![-\d])/g, 'stand by'],
  [/(?<![-\d])1039(?![-\d])/g, 'notified'],
  [/(?<![-\d])1021(?![-\d])/g, 'phone call'],
  [/(?<![-\d])23103(?![-\d])/g, 'reckless driving'],
  [/(?<![-\d])23114(?![-\d])/g, 'spilled load'],
  [/(?<![-\d])20001(?![-\d])/g, 'felony hit and run'],
  [/(?<![-\d])20002(?![-\d])/g, 'hit and run, property damage'],
  [/(?<![-\d])23152(?![-\d])/g, 'possible DUI'],
  [/(?<![-\d])22350(?![-\d])/g, 'unsafe speed'],
  [/(?<![-\d])5150(?![-\d])/g, 'mental health hold'],
  // Radio chatter drops the leading 11 from injury codes.
  [/(?<![-\d])\b180\b(?![-\d])/g, 'major injuries'],
  [/(?<![-\d])\b144\b(?![-\d])/g, 'fatality'],
  [/(?<![-\d])\b415\b(?![-\d])/g, 'a dispute'],
  [/\b97\b/g, 'on scene'],
  // Word tokens.
  [/\bTC\b/g, 'collision'], [/\bVEHS\b/g, 'vehicles'], [/\bVEH\b/g, 'vehicle'],
  [/\bPED\b/g, 'pedestrian'], [/\bMC\b/g, 'motorcycle'],
  [/\bTRLR\b/g, 'trailer'], [/\bBLKG\b/g, 'blocking'],
  [/\bENRT\b/g, 'en route'],
  [/\bNEG\b/g, 'no'], [/\bPOSS\b/g, 'possible'], [/\bUNKN?\b/g, 'unknown'],
  [/\bRHS\b/g, 'right-hand shoulder'], [/\bLHS\b/g, 'left-hand shoulder'],
  [/\bCD\b/g, 'center divider'], [/\bOFR\b/g, 'off-ramp'],
  [/\bONR\b/g, 'on-ramp'], [/\bJSO\b/g, 'just south of'],
  [/\bJNO\b/g, 'just north of'], [/\bJEO\b/g, 'just east of'],
  [/\bJWO\b/g, 'just west of'], [/\bIFO\b/g, 'in front of'],
  [/\bNB\b/g, 'northbound'],
  [/\bSB\b/g, 'southbound'], [/\bEB\b/g, 'eastbound'],
  [/\bWB\b/g, 'westbound'], [/\bLNS\b/g, 'lanes'], [/\bLN\b/g, 'lane'],
  [/\bPK\b/g, 'pickup'], [/\bTK\b/g, 'truck'], [/\bTRK\b/g, 'truck'],
  [/\bSD\b/g, 'sedan'], [/\bSEMI\b/g, 'semi-truck'],
  [/\bFSP\b/g, 'Freeway Service Patrol'],
  [/\bXFER\b/g, 'transferred to'],
  [/\bADVSD\b/g, 'advised'], [/\bADVD\b/g, 'advised'],
  [/\bADV\b/g, 'advised'], [/\bLL\b/g, 'landline call'],
  [/\bREQ\b/g, 'requesting'], [/\bRESP\b/g, 'respond'],
  [/\bINJS\b/g, 'injuries'], [/\bINJ\b/g, 'injuries'],
  [/\bDMG\b/g, 'damage'], [/\bCONT\b/g, 'continued'],
  [/\bRDWY\b/g, 'road'], [/\bDRVR\b/g, 'driver'],
  [/\bDESC\b/g, 'description'], [/\bVICT\b/g, 'victim'],
  [/\bSUSP\b/g, 'suspect'], [/\bINVLVD\b/g, 'involved'],
  [/\bINVLD\b/g, 'involved'],
  [/\bSV\b/g, 'the subject vehicle'], [/\bVV\b/g, 'the victim vehicle'],
  [/\bWW\b/g, 'the wrong way'], [/\bXRAY\b/g, 'a female'],
  [/\bOO\b/g, 'out of'],
  [/\bUTL\b/g, 'unable to locate'], [/\bGOA\b/g, 'gone on arrival'],
  [/\bHBD\b/g, 'had been drinking'], [/\bCDF\b/g, 'CAL FIRE'],
  [/\bFB\b/g, 'flatbed'], [/\bCR ?(\d+)\b/g, 'County Road $1'],
  [/\bW\//g, 'with '], [/\bFRM\b/g, 'from'],
  [/\bRPS\b/g, "the caller's"], [/\bRP\b/g, 'the caller'],
  [/\bTT\b/g, 'tow truck'], [/\bPLS\b/g, 'please'],
  [/\bAPPRO[XZ]\b/g, 'approximately'],
  [/\bPTYS\b/g, 'people'], [/\bPRTYS\b/g, 'people'],
  [/\bPTY\b/g, 'person'], [/\bPRTY\b/g, 'person'],
  [/\bRD\b/g, 'Road'],
  // Vehicle makes and colors, as CHP abbreviates them.
  [/\bTOYT\b/g, 'Toyota'], [/\bHOND\b/g, 'Honda'], [/\bCHEV\b/g, 'Chevrolet'],
  [/\bNISS\b/g, 'Nissan'], [/\bFORD\b/g, 'Ford'], [/\bDODG\b/g, 'Dodge'],
  [/\bSUBA\b/g, 'Subaru'], [/\bHYUN\b/g, 'Hyundai'], [/\bVOLK\b/g, 'Volkswagen'],
  [/\bMERZ\b/g, 'Mercedes'], [/\bTESL\b/g, 'Tesla'], [/\bMAZD\b/g, 'Mazda'],
  [/\bLEXS\b/g, 'Lexus'], [/\bTOYO\b/g, 'Toyota'], [/\bVOLV\b/g, 'Volvo'],
  [/\bToyota TAC\b/g, 'Toyota Tacoma'], [/\bToyota CAM\b/g, 'Toyota Camry'],
  [/\bWHI\b/g, 'white'], [/\bBLK\b/g, 'black'], [/\bGRY\b/g, 'gray'],
  [/\bSIL\b/g, 'silver'], [/\bBLU\b/g, 'blue'], [/\bGRN\b/g, 'green'],
  [/\bYEL\b/g, 'yellow'], [/\bORG\b/g, 'orange'], [/\bBRO\b/g, 'brown'],
];
function explainLine(text) {
  // Official hyphenated labels ("1179-Trfc Collision-1141 Enrt") must
  // survive verbatim: translating codes inside them garbles the
  // label, so mask them before translating and restore after.
  const keep = [];
  const masked = (text || '').replace(/\d{4}[A-Z]?-\S[^,\[\]]*/g, (s) => {
    keep.push(s);
    return '\u0001' + (keep.length - 1) + '\u0001';
  });
  let out = masked;
  for (const [re, plain] of CHP_TERMS) out = out.replace(re, plain);
  const changed = out !== masked;
  out = out.replace(/\u0001(\d+)\u0001/g, (x, i) => keep[+i]);
  return changed ? out : null;
}
function fmtNowDay() {
  return new Date().toLocaleString([], {
    hour: 'numeric', minute: '2-digit', weekday: 'long' });
}
const CHAIN_GLOSS = {
  'R-1': 'R-1: chains or approved snow tires required. Carry chains even with snow tires.',
  'R-2': 'R-2: chains required on every vehicle except 4WD/AWD with snow tires on all four - and even those must carry chains.',
  'R-3': 'R-3: chains on every vehicle, no exceptions. Roads at R-3 often close soon after.',
};

function agoTxt(iso) {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return null;
  const mins = Math.round((Date.now() - t) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return mins + ' min ago';
  if (mins < 48 * 60) {
    const h = Math.round(mins / 60);
    return h + (h === 1 ? ' hour ago' : ' hours ago');
  }
  return Math.round(mins / 1440) + ' days ago';
}
function clockTxt(epoch) {
  if (!epoch) return null;
  const d = new Date(epoch * 1000);
  const opts = { hour: 'numeric', minute: '2-digit' };
  if (Math.abs(d - Date.now()) > 20 * 3600 * 1000) opts.weekday = 'short';
  return d.toLocaleString([], opts);
}
function histBlock(bits) {
  const keep = bits.filter(Boolean);
  return keep.length ? '<div class="hist">' + keep.join('<br>') + '</div>' : '';
}

// ============ v2 popup card system (2026-07 redesign) ============
// One accent color per kind, used only in the header chip and rail.
const ACC = { inc: '#c9611a', clo: '#a02c2c', clo_full: '#7f1d1d',
  chain: '#2b6cb0', rwis: '#2f9e6e', fire: '#d97706', camera: '#2f81f7',
  sign: '#a16207', plugin: '#0e9f9f' };
const humanize = (t) => {
  if (!t) return null;
  let s = String(t).replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim();
  if (s === s.toUpperCase()) s = s.toLowerCase();
  else s = s.charAt(0).toLowerCase() + s.slice(1);
  return s.charAt(0).toUpperCase() + s.slice(1);
};
// An incident's title in plain words. CHP types arrive as dispatch code
// plus scanner shorthand ("1179-Trfc Collision-1141 Enrt"); the codes
// this table knows read as the same plain sentence chpGloss explains,
// and anything else has its abbreviations spelled out and its code
// dropped. The raw type stays in the details pane's Advanced view.
const INCIDENT_TITLES = [
  [/^1179\b/, 'Crash, ambulance on the way'],
  [/^1180\b/, 'Crash, major injuries'],
  [/^1181\b/, 'Crash, minor injuries'],
  [/^1182\b/, 'Crash, no injuries'],
  [/^1183\b/, 'Crash, injuries unknown'],
  [/^1125A\b/, 'Animal on the road'],
  [/^1125\b/, 'Traffic hazard'],
  [/^20001\b/, 'Hit and run with injuries'],
  [/^20002\b/, 'Hit and run, no injuries'],
  [/^23114\b/, 'Spilled load on the road'],
  [/^1166\b/, 'Traffic signals not working'],
  [/^1013\b/, 'Road or weather conditions'],
  [/^CZP\b/, 'Officers at a work zone'],
  [/^MZP\b/, 'Officers at a maintenance zone'],
  [/^SIG\b/i, 'SIG Alert: major incident'],
  [/^CLOSURE\b/, 'Road closed'],
  [/^CHAINS\b/, 'Chain control'],
  [/^FLOOD\b/, 'Flooding on the road'],
  [/^FOG\b/, 'Fog'],
  [/^WIND\b/, 'Wind advisory'],
  [/^SNOW\b/, 'Snow on the road'],
  [/^ANIMAL\b/, 'Animal on the road'],
  [/^FIRE\b/, 'Fire reported'],
  [/^TADV\b/, 'Traffic advisory'],
  [/^ESCORT\b/, 'Escort for road conditions'],
  [/^SILVER\b/, 'Silver Alert'],
  [/^SPINOUT$/, 'Vehicle spun out'],
  [/^DeadAnimal/, 'Dead animal on the road'],
];
const SHORTHAND = [
  [/\bTrfc\b/gi, 'traffic'], [/\bColl\b/gi, 'collision'], [/\bInj\b/gi, 'injuries'],
  [/\bUnkn?\b/gi, 'unknown'], [/\bEnrt\b/gi, 'en route'], [/\bVeh\b/gi, 'vehicle'],
  [/\bAmb\b/gi, 'ambulance'], [/\bRd\b/gi, 'road'], [/\bHwy\b/g, 'highway'],
  [/\bRshoulder\b/gi, 'right shoulder'], [/\bLshoulder\b/gi, 'left shoulder'],
];
function incidentTitle(type) {
  const t = String(type || '').trim();
  if (!t) return null;
  for (const [re, text] of INCIDENT_TITLES) if (re.test(t)) return text;
  let s = t.replace(/^\d{4,5}[A-Z]?\s*[-:]\s*/, '')
    .replace(/(Rshoulder|Lshoulder)/g, ' $1');
  for (const [re, word] of SHORTHAND) s = s.replace(re, word);
  s = humanize(s.replace(/\s+-\s+/g, ', ').replace(/^(Debris|Crash|Vehicle) (right|left) shoulder$/i, '$1 on the $2 shoulder'));
  // Sentence case: "Abandoned Vehicle" reads as "Abandoned vehicle";
  // short all-caps words (CT, US) and route numbers keep their case.
  return s ? s.replace(/(?!^)\b([A-Z])([a-z]+)\b/g, (w, a, b) => a.toLowerCase() + b) : null;
}
// ALL-CAPS operator dumps ("CLOSED DUE TO X//USE Y/ STAY ALERT") read
// as shouting: sentence-case them and split the slash chains into
// real sentences. Route numbers stay caps.
function shapeShout(t) {
  if (!t) return t;
  const letters = t.replace(/[^A-Za-z]/g, '');
  const caps = letters.replace(/[^A-Z]/g, '');
  if (!letters.length || caps.length / letters.length < 0.8) return t;
  return t.split(/\s*\/{1,2}\s*/).filter(Boolean).map((seg) => {
    seg = seg.toLowerCase().trim();
    seg = seg.replace(/\b(us|i|sr|nv|ca|az|ut|wa|or|id|co|nm|mt|wy|nd|sd)-?(\d+[a-z]*)\b/g,
      (x, p, n) => p.toUpperCase() + '-' + n.toUpperCase());
    return seg.charAt(0).toUpperCase() + seg.slice(1) +
      (/[.!?]$/.test(seg) ? '' : '.');
  }).join(' ');
}
// "US 89: Emergency Maintenance, NB State St..." -> road + rest
const splitRoad = (label) => {
  const m = /^([A-Z]{1,3}[- ]?\d+[A-Z]?(?:\/[A-Z0-9-]+)?)\s*[:-]\s*(.+)$/.exec(label || '');
  return m ? { road: m[1], rest: m[2] } : { road: null, rest: label };
};
function v2(acc, kindLabel, ago, title, sub, bodyRows, facts, foot, extraHtml) {
  return '<div class="p2" style="--acc:' + acc + '">' +
    '<div class="hd"><span class="kchip"><i></i>' + kindLabel + '</span>' +
    (ago ? '<span class="ago">' + ago + '</span>' : '') + '</div>' +
    (title ? '<h4>' + title + '</h4>' : '') +
    (sub ? '<div class="sub">' + sub + '</div>' : '') +
    (bodyRows || []).filter(Boolean).map((b) =>
      '<div class="body' + (b.gloss ? ' gloss' : '') + '">' +
      (b.text || b) + '</div>').join('') +
    ((facts || []).filter((f) => f && f[1]).length
      ? '<div class="facts">' + facts.filter((f) => f && f[1]).map((f) =>
        '<div class="fact"><b>' + f[0] + '</b><span>' + f[1] + '</span></div>')
        .join('') + '</div>' : '') +
    (extraHtml || '') +
    ((foot || []).filter(Boolean).length
      ? '<div class="foot">' + foot.filter(Boolean).map((x) =>
        '<em>' + x + '</em>').join('') + '</div>' : '') +
    '</div>';
}
// Times render in the ROAD's timezone; when that differs from the
// viewer's, the schedule panel adds an auto-converted line. Every
// marker source maps to its state's zone (states that span zones get
// the zone covering most of their road network).
const VIEWER_TZ = Intl.DateTimeFormat().resolvedOptions().timeZone;
const TZ_BY_SRC = {
  'WSDOT': 'America/Los_Angeles',
  'Oregon DOT (TripCheck)': 'America/Los_Angeles',
  'NDOT': 'America/Los_Angeles',
  '511.org': 'America/Los_Angeles', 'BATA': 'America/Los_Angeles',
  'GGB': 'America/Los_Angeles',
  'Alaska DOT&PF': 'America/Anchorage',
  'HDOT': 'Pacific/Honolulu',
  'ITD': 'America/Boise',
  'UDOT': 'America/Denver', 'CDOT': 'America/Denver',
  'ADOT': 'America/Phoenix',
  'WisDOT': 'America/Chicago', 'MnDOT': 'America/Chicago',
  'KDOT': 'America/Chicago', 'MoDOT': 'America/Chicago',
  'ODOT (OK)': 'America/Chicago', 'Louisiana DOTD': 'America/Chicago',
  'City of Austin': 'America/Chicago', 'Iowa DOT': 'America/Chicago',
  'TravelMidwest (IDOT)': 'America/Chicago',
  'MDOT Traffic (MS)': 'America/Chicago',
  'TDOT SmartWay': 'America/Chicago',
  'ALGO Traffic (ALDOT)': 'America/Chicago',
  'NTTA': 'America/Chicago', 'HCTRA': 'America/Chicago',
  'MDOT MiDrive': 'America/Detroit',
  '511NY': 'America/New_York', 'NJDOT': 'America/New_York',
  'MDOT SHA': 'America/New_York', 'MDOT CHART': 'America/New_York',
  'KYTC': 'America/New_York', 'DelDOT': 'America/New_York',
  'FDOT': 'America/New_York', 'FDOT (WZDx)': 'America/New_York',
  'NCDOT': 'America/New_York', 'CTDOT': 'America/New_York',
  'MaineDOT': 'America/New_York', 'NHDOT': 'America/New_York',
  'VTrans': 'America/New_York', 'VDOT': 'America/New_York',
  'OHGO': 'America/New_York',
  'INDOT': 'America/Indiana/Indianapolis',
};
// No src = California.
const roadTz = (m) => (m && TZ_BY_SRC[m.src]) || 'America/Los_Angeles';
const zoneAbbr = (t, tz) => (new Intl.DateTimeFormat('en-US',
  { timeZone: tz, timeZoneName: 'short' }).formatToParts(t)
  .find((p) => p.type === 'timeZoneName') || {}).value || '';
const sameClock = (t, a, b) =>
  t.toLocaleString('en-US', { timeZone: a }) ===
  t.toLocaleString('en-US', { timeZone: b });
// zoneMode: 0 = no zone, 1 = zone abbreviation, 2 = zone abbreviation
// plus "(your timezone)" when it matches the viewer's.
function whenPhrase(epoch, tz, zoneMode) {
  if (!epoch) return null;
  tz = tz || 'America/Los_Angeles';
  const t = new Date(epoch * 1000);
  const now = new Date();
  const clock = t.toLocaleTimeString([], {
    hour: 'numeric', minute: '2-digit', timeZone: tz });
  const ymd = (d) => d.toLocaleDateString('en-CA', { timeZone: tz });
  const dayGap = Math.round(
    (Date.parse(ymd(t)) - Date.parse(ymd(now))) / 86400000);
  const hr = +t.toLocaleString('en-US', {
    hour: 'numeric', hour12: false, timeZone: tz });
  let day;
  if (dayGap === 0) day = hr >= 18 ? 'tonight' : 'today';
  else if (dayGap === 1) day = 'tomorrow';
  else if (dayGap === -1) day = 'yesterday';
  else day = t.toLocaleDateString([], { weekday: 'long', timeZone: tz })
    + (Math.abs(dayGap) > 6
      ? ', ' + t.toLocaleDateString([], { month: 'short', day: 'numeric', timeZone: tz }) : '')
    + (Math.abs(dayGap) > 300
      ? ', ' + t.toLocaleDateString([], { year: 'numeric', timeZone: tz }) : '');
  let s = day + ' at ' + clock;
  if (zoneMode) {
    s += ' ' + zoneAbbr(t, tz);
    if (zoneMode === 2 && sameClock(t, tz, VIEWER_TZ)) s += ' (your timezone)';
  }
  return s;
}
function spanPhrase(epoch) {
  if (!epoch) return null;
  const mins = Math.round(Math.abs(Date.now() / 1000 - epoch) / 60);
  if (mins < 60) return mins + ' minutes';
  if (mins < 60 * 36) {
    const h = Math.round(mins / 60);
    return 'about ' + h + (h === 1 ? ' hour' : ' hours');
  }
  const d = Math.round(mins / 1440);
  return 'about ' + d + (d === 1 ? ' day' : ' days');
}
function schedPanel(m) {
  // Copy spec: never promote a schedule into an observation. The
  // "scheduled to end" frame survives every state; hedges only from
  // the approved list; "reopen"/"in effect"/"may" are banned.
  const now = Date.now() / 1000;
  const agency = m.src ? esc(m.src) : 'Caltrans';
  const tz = roadTz(m);
  // Conversion block: the start and the scheduled end, full date and
  // time, each on its own line. Rendered only when the viewer's
  // timezone actually differs from the road's.
  const fullWhen = (epoch, tzz) => {
    const t = new Date(epoch * 1000);
    return t.toLocaleDateString([], { weekday: 'long', month: 'short',
      day: 'numeric', timeZone: tzz }) + ' at ' +
      t.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit',
      timeZone: tzz }) + ' ' + zoneAbbr(t, tzz);
  };
  const tzBlock = () => {
    const rows = [['Start', m.since], ['Scheduled end', m.until]]
      .filter((r) => r[1]);
    if (!rows.length) return '';
    const differs = rows.some(([, ep]) =>
      !sameClock(new Date(ep * 1000), tz, VIEWER_TZ));
    if (!differs) return '';
    return '<span class="tzl">In your timezone:' +
      rows.map(([lbl, ep]) =>
        '<br>' + lbl + ': ' + fullWhen(ep, VIEWER_TZ)).join('') +
      '</span>';
  };
  let head, tail, extra = '';
  if (m.until && m.until < now) {
    head = 'Was scheduled to end ' + whenPhrase(m.until, tz, 2);
    tail = 'That was ' + spanPhrase(m.until) + ' ago. ' +
      (m.cls === 'full-roadway'
        ? agency + ' has not reported it open. Assume the road is still closed.'
        : agency + ' has not reported it clear. Assume the restriction is still there.');
    extra = tzBlock();
  } else if (m.until) {
    head = 'Scheduled to end ' + whenPhrase(m.until, tz, 2);
    tail = 'That is ' + spanPhrase(m.until) + ' from now.' +
      (m.since ? ' It started ' + whenPhrase(m.since, tz) + '.' : '');
    extra = tzBlock();
  } else {
    head = 'No scheduled end';
    // "The road stays closed" is only true for a full closure; a lane
    // or shoulder restriction gets the accurate weaker claim.
    tail = (m.cls === 'full-roadway'
      ? 'The road stays closed until ' + agency + ' reports it open.'
      : 'The restriction stays until ' + agency + ' reports it clear.') +
      (m.since ? ' It started ' + whenPhrase(m.since, tz) + '.' : '');
    extra = tzBlock();
  }
  return '<div class="sched"><b>' + head + '</b><span>' + tail +
    '</span>' + extra + '</div>';
}
const CHAIN_LEVELS = [
  ['R-1', 'Chains or approved snow tires required. Carry chains even with snow tires.'],
  ['R-2', 'Chains required on every vehicle, except 4WD/AWD with snow tires on all four wheels. Even those must carry chains.'],
  ['R-3', 'Chains required on every vehicle, no exceptions. Plan for a full closure.'],
];
const COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
  'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
// Caltrans ships degrees, Travel-IQ ships compass strings: show both
// the same way.
const windDirTxt = (d) =>
  typeof d === 'number' ? COMPASS[Math.round(d / 22.5) % 16] : d;
const windDirDeg = (d) =>
  typeof d === 'number' ? d : COMPASS.indexOf(String(d).toUpperCase()) * 22.5;
// Tiny compass: ring with N tick, needle pointing at the direction
// the wind comes from (matching the "from the NNE" text).
const compassSvg = (deg) =>
  '<svg class="cmp" viewBox="0 0 20 20" width="15" height="15" aria-hidden="true">' +
  '<circle cx="10" cy="10" r="8.5" fill="none" stroke="#cbd5e1" stroke-width="1.6"/>' +
  '<rect x="9.4" y="0" width="1.2" height="3" fill="#94a3b8"/>' +
  '<path d="M10 4.2 L12.4 13 L10 11.4 L7.6 13 Z" fill="#0f766e"' +
  ' transform="rotate(' + deg + ' 10 10)"/></svg>';

// Camera URLs come from state feeds (and from our own /api/stcam
// proxy), and they land in src and href attributes. Two rules:
//   - Only http(s) or a same-origin path survives, so a javascript:
//     URL in a feed can never become a clickable link.
//   - Escape for the attribute, never re-encode. encodeURI() used to do
//     the encoding here and corrupted every proxy URL, whose camera ids
//     are already percent-encoded server-side (a space became %2520 and
//     the fetch 404'd, which broke all ME/NH/VT snapshots).
function safeUrl(u) {
  const s = String(u == null ? '' : u);
  const ok = /^https?:\/\//i.test(s) || (s[0] === '/' && s[1] !== '/');
  return ok ? s.replace(/&/g, '&amp;').replace(/"/g, '&quot;')
    .replace(/</g, '&lt;').replace(/>/g, '&gt;') : '';
}

function popupFor(m, g) {
  if (g === 'camera') {
    const img = safeUrl(m.image);
    const vid = safeUrl(m.stream);
    // The media type is the first thing a user should know: a still
    // that refreshes on open is not the same promise as live video.
    const chip = vid
      ? '<span class="mchip live">Live video</span>'
      : '<span class="mchip">Still snapshot</span>';
    return '<div class="p2" style="--acc:' + ACC.camera + '">' +
      '<div class="hd"><span class="kchip"><i></i>Camera</span>' + chip + '</div>' +
      '<h4>' + esc(m.name || 'Roadside camera') + '</h4>' +
      '<div class="sub">' + esc([[m.route, m.direction].filter(Boolean).join(' '),
        m.near].filter(Boolean).join(', ')) + '</div>' +
      // no-referrer: some state camera hosts (TravelMidwest) 403 any
      // request carrying a foreign Referer header.
      (img
        ? '<img src="' + img + '?t=' + Date.now() + '" width="300" ' +
          'referrerpolicy="no-referrer" ' +
          'alt="" onerror="this.replaceWith(document.createTextNode(\'snapshot unavailable right now\'))">'
        : '') +
      (vid
        ? '<div><a class="detbtn" href="' + vid +
          '" target="_blank" rel="noopener">Watch the live stream</a></div>'
        : '') +
      // Straight to the agency's own image, at whatever size they
      // publish: the popup only ever shows a 300px copy. noreferrer for
      // the same reason the <img> above carries it.
      (img
        ? '<div><a class="detbtn" href="' + img +
          '" target="_blank" rel="noopener noreferrer">Open the full image</a></div>'
        : '') +
      (vid ? '' : '<div class="camnote">Still image, not video. ' +
        'A new image loads each time you open this camera.</div>') +
      '<div class="foot"><em>Source: ' +
      (m.src ? esc(m.src) + ' camera network' : 'Caltrans CCTV') +
      '</em></div></div>';
  }
  if (g === 'sign') {
    const lines = (m.lines && m.lines.length)
      ? m.lines : (m.message ? m.message.split(' / ') : []);
    return v2(ACC.sign, 'Message sign', null,
      esc([m.route, m.direction].filter(Boolean).join(' ') || 'Changeable sign'),
      esc(m.near || ''),
      [!lines.length ? { text: 'This sign is blank right now.', gloss: true } : null],
      [], ['Source: ' + (m.src ? esc(m.src) + ' message signs' : 'Caltrans CMS')],
      lines.length ? '<div class="cmsboard">' +
        lines.map((l) => '<span>' + esc(l) + '</span>').join('') + '</div>' : '');
  }
  if (g === 'toll') {
    const money = (v) => '$' + v.toFixed(2).replace(/\.00$/, '');
    const req = m.toll_type === 'required';
    const bridge = m.src === 'BATA' || m.src === 'GGB';
    const typeChip = req
      ? '<span class="chip req">' + (bridge ? 'TOLL BRIDGE' : 'ALL LANES TOLLED') + '</span>'
      : '<span class="chip opt">OPTIONAL EXPRESS LANE</span>';
    const liveChip = m.pricing === 'live'
      ? '<span class="chip live"><i></i>LIVE</span>'
      : '<span class="chip fixed">' + (m.as_of ? 'POSTED RATE' : 'FIXED RATE') + '</span>';
    const range = (m.min === m.max) ? money(m.min)
      : money(m.min) + '–' + money(m.max);
    const entries = (m.entries || []).filter((e) => (e.rows || []).length);
    // Time saved, where the agency publishes lane-vs-lane travel
    // times (WSDOT): the honest answer to "is the toll worth it".
    let save = '';
    if (m.gp_min != null && m.lane_min != null) {
      const d = m.gp_min - m.lane_min;
      save = d >= 2
        ? '<div class="tsave">Express lanes ' + m.lane_min + ' min vs ' +
          m.gp_min + ' min in regular lanes: <b>saves ~' + d + ' min now</b></div>'
        : '<div class="tsave">Regular lanes moving freely right now (' +
          m.gp_min + ' min)</div>';
    }
    // Copy spec: direction first so the driver matches on it before
    // reading; "may" is banned.
    const OPP_DIR = { westbound: 'Eastbound', eastbound: 'Westbound',
      northbound: 'Southbound', southbound: 'Northbound' };
    const dirLine = m.toll_dir
      ? '<div class="d" style="margin-top:4px"><b>' +
        esc(humanize(m.toll_dir)) +
        (m.toll_note ? ', ' + esc(m.toll_note) : '') + ': toll.</b> ' +
        esc(OPP_DIR[(m.toll_dir || '').toLowerCase()] || 'The other direction') +
        ': free.</div>'
      : '';
    const freshness = m.as_of
      ? 'Posted rates, effective ' + esc(m.as_of)
      : (m.updated ? (function () {
          const mins = (Date.now() - Date.parse(m.updated)) / 60000;
          if (!(mins >= 0)) return null;
          if (mins < 120) return 'Updated ' + (agoTxt(m.updated) || 'recently');
          // Express-lane signs stop updating when the lanes are open
          // to everyone (nights, weekends): say when the rate is FROM
          // instead of pretending it is current.
          return 'Rates from ' + new Date(m.updated).toLocaleString([],
            { weekday: 'short', hour: 'numeric', minute: '2-digit' }) +
            (req ? '' : '. Lanes can be open to all right now');
        })() : null);
    const rows = entries.map((e, gi) => {
      const head = req
        ? '<div class="tfrom" data-tg="' + gi + '">' + esc(e.label) + '</div>'
        : '<div class="tfrom" data-tg="' + gi + '">From ' + esc(e.label) + '</div>';
      return head + (e.rows || []).map((r, ri) =>
        '<div class="trow" data-tg="' + gi + '" data-td="' + ri + '">' +
        '<span class="td">' + (r[0] ? (req ? esc(r[0]) : 'to ' + esc(r[0])) : 'per pass') +
        '</span><span class="tdots"></span><span class="tp">' + money(r[1]) +
        '</span></div>').join('');
    }).join('');
    return popHead(g, m.corridor || m.name || 'Toll') +
      '<div class="tpop">' +
      '<div class="thead">' + typeChip + liveChip + '</div>' +
      '<div class="trange">' + range +
      (entries.length > 1 ? ' <small>now, ' + entries.length +
        ' entry points</small>' : '') + '</div>' + dirLine + save +
      (rows ? '<details open><summary>All rates' +
        (entries.length > 1 ? ' (hover to see on the map)' : '') +
        '</summary><div class="tbody">' + rows + '</div></details>' : '') +
      histBlock([
        req ? 'Required toll: every vehicle pays here'
            : 'Optional: the regular lanes are free',
        freshness,
        m.src === '511.org' ? 'Toll data provided by 511.org'
          : m.src === 'BATA' ? 'Posted schedule, Bay Area Toll Authority'
          : m.src === 'GGB' ? 'Posted schedule, Golden Gate Bridge District'
          : m.src ? 'Prices provided by ' + esc(m.src) : null]) +
      '</div></div>';
  }
  if (g === 'rwis') {
    const f = (c) => Math.round(c * 9 / 5 + 32) + '&deg;F';
    // A direction on calm wind ("0 mph from the E") is noise.
    const dir = (m.wind_dir != null && !(m.wind != null && Math.round(m.wind) < 1))
      ? esc(windDirTxt(m.wind_dir)) : null;
    const gustTail = m.gust != null
      ? ', gusts ' + Math.round(m.gust) + ' mph' : '';
    const facts = [
      m.air_c != null ? ['Air', f(m.air_c)] : null,
      m.pave_c != null ? ['Pavement', f(m.pave_c)] : null,
      m.wind != null
        ? ['Wind', (dir ? compassSvg(windDirDeg(m.wind_dir)) : '') +
            Math.round(m.wind) + ' mph' +
            (dir ? ' from the ' + dir : '') + gustTail]
        : (m.gust != null
          ? ['Wind', (dir ? compassSvg(windDirDeg(m.wind_dir)) : '') +
              'gusts ' + Math.round(m.gust) + ' mph' +
              (dir ? ' from the ' + dir : '')] : null),
      m.rh != null ? ['Humidity', Math.round(m.rh) + '%'] : null,
      m.precip ? ['Precip', esc(humanize(m.precip))] : null,
      m.surface ? ['Surface', esc(m.surface)] : null,
      m.vis_m != null && m.vis_m < 5000
        ? ['Visibility', Math.round(m.vis_m) + ' m'] : null,
    ];
    const none = !facts.some(Boolean);
    return v2(ACC.rwis, 'Road weather', null,
      esc(m.station || m.name || 'Weather station'),
      esc(m.route || ''),
      [none ? { text: 'This station is online. It has no readings right now.', gloss: true } : null],
      facts, ['Source: ' + (m.src ? esc(m.src) + ' weather station'
        : 'Caltrans roadside weather station')]);
  }
  if (g === 'plugin') {
    // A Flare plugin alert: what it is, where, how sure, and who says so.
    // A camera reads the way people say it ("Speed camera", not "Camera
    // speed"), and its description opens with those same words, so they
    // come off the line under the title.
    const camera = { CAMERA_SPEED: 'Speed camera', CAMERA_RED_LIGHT: 'Red light camera' }[m.flare_kind];
    const kindTxt = camera || esc(humanize((m.flare_kind || 'OTHER').toLowerCase().replace(/_/g, ' ')));
    let about = m.label || '';
    if (camera && about.toLowerCase().startsWith(camera.toLowerCase())) {
      about = about.slice(camera.length).replace(/^[,.\s]+/, '');
      about = about.charAt(0).toUpperCase() + about.slice(1);
    }
    // Something fixed in place was not "reported 38 minutes ago".
    const fixed = (m.ttl_s || 0) >= 86400;
    const n = Number(m.confirmations) || 0;
    const facts = [
      m.road ? ['Road', esc(m.road)] : null,
      n ? ['Confirmed', n + (n === 1 ? ' time' : ' times')] : null,
      (m.reliability != null && !fixed) ? ['Reliability', Math.round(m.reliability * 100) + '%'] : null,
      m.data ? ['Data from', esc(m.data)] : null,
    ];
    return v2(csPlugin.color(csPlugin.sourceId(m)), esc(m.source || 'Plugin'),
      m.reported && !fixed ? agoTxt(m.reported) : null,
      kindTxt, about ? esc(about) : null, [], facts, [
        'Source: ' + esc(m.source || 'community plugin') +
          (m.tier === 'approved' ? ' (approved by CommuteScout)'
            : m.tier === 'unreviewed' ? ' (public, not reviewed)'
            : m.trust ? ' (' + esc(m.trust) + ')' : ''),
        /^https:\/\//.test(m.source_url || '')
          ? '<a href="' + esc(m.source_url) + '" target="_blank" rel="noopener">More</a>' : null,
      ]);
  }
  if (g && g.startsWith('inc_')) {
    const parts = splitRoad(m.label || '');
    // esc(): m.type is CHP LogType feed text, and v2() drops title into
    // <h4> as raw HTML (callers pre-escape, like the toll_dir site).
    const title = esc(incidentTitle(m.type) || 'Incident');
    const sub = m.location || parts.road || null;
    const body = [];
    const gloss = chpGloss(m.type);
    // Out-of-state feeds ship a clean `detail` sentence; the templated
    // `label` dump only fills in when there is nothing better.
    if (m.detail && m.detail !== m.label) body.push(esc(shapeShout(m.detail)));
    else if (m.label && m.label !== m.location) body.push(esc(parts.rest || m.label));
    if (gloss) body.push({ text: gloss, gloss: true });
    const facts = [
      parts.road && !m.location ? ['Road', esc(parts.road)] : null,
      m.dir ? ['Direction', 'Affects the ' + esc(m.dir) + ' side'] : null,
      m.lanes ? ['Lanes', esc(m.lanes)] : null,
    ];
    const foot = [
      m.reported ? 'Reported ' + agoTxt(m.reported) : 'Live report',
      'Source: ' + (m.src ? esc(m.src) + ' data feed'
            : 'CHP ' + (m.area ? esc(m.area) + ' ' : '') + 'dispatch'),
    ];
    const btn = (m.id && m.log_n)
      ? '<button type="button" class="detbtn" data-inc="' + esc(m.id) +
        '">Show dispatch log (' + m.log_n + ')</button><div class="dets"></div>'
      : '';
    return v2(ACC.inc, 'Incident', m.reported ? agoTxt(m.reported) : null,
      title, sub ? esc(sub) : null, body, facts, foot, btn);
  }
  if (g && g.startsWith('clo_')) {
    const kindLbl = { clo_full: 'Road closed', clo_lane: 'Lanes closed',
      clo_oneway: 'One-way traffic', clo_ramp: 'Ramp closed' }[g] || 'Closure';
    const acc = g === 'clo_full' ? ACC.clo_full : ACC.clo;
    const warn = (m.cls === 'full-roadway' || /all lanes/i.test(m.lanes || ''))
      ? 'All lanes closed' : (m.lanes || null);
    // Out-of-state markers carry a shaped `detail` sentence; the raw
    // label dump is the fallback, not the default.
    const prose = shapeShout(m.detail || m.label);
    return v2(acc, kindLbl, null,
      esc([m.route, m.county].filter(Boolean).join(', ') || 'Closure'),
      m.dir ? esc(m.dir) : null,
      [warn ? { text: '<span class="warnline">' + esc(warn) + '</span>' } : null,
       prose ? esc(prose) : null],
      [
        m.work ? ['Work', esc(humanize(m.work))] : null,
        m.delay_min ? ['Delay', '~' + m.delay_min + ' min expected'] : null,
        (m.facility && m.cls === 'ramp') ? ['Facility', esc(m.facility)] : null,
        m.windows ? ['Windows', (m.windows - 1) + ' more scheduled at this spot'] : null,
      ],
      ['Source: ' + (m.src ? esc(m.src) + ' data feed'
        : 'Caltrans lane closure system')],
      schedPanel(m));
  }
  if (g === 'chain') {
    // The R system is California's. Other agencies (WSDOT mountain
    // passes) publish free-text restrictions: show those verbatim,
    // no R legend.
    if (m.src) {
      const parts = [...new Set((m.label || '').split(/;\s*/)
        .map((s) => s.trim()).filter(Boolean))];
      const noinfo = /no current information/i.test(m.label || '');
      return v2(ACC.chain, 'Pass restriction',
        m.updated ? agoTxt(m.updated) : null,
        esc(m.route || m.status || 'Mountain pass'), null,
        [noinfo
          ? { text: esc(m.src) + ' has not posted current restrictions for this pass.', gloss: true }
          : (parts.length
            ? esc(parts.join('. ') + (/[.!?]$/.test(parts[parts.length - 1]) ? '' : '.'))
            : null)],
        [], ['Source: ' + esc(m.src) + ' mountain pass reports']);
    }
    // What applies now gets the bold panel; the other tiers sit below
    // as quiet reference so the level has meaning.
    const norm = (m.status || '').toUpperCase().replace(/^R(\d)$/, 'R-$1');
    const active = CHAIN_LEVELS.find(([k]) => k === norm);
    const others = CHAIN_LEVELS.filter(([k]) => k !== norm);
    let extra;
    if (active) {
      extra = '<div class="sched"><b>Caltrans reports ' + norm +
        ' here</b><span>' + active[1] + '</span></div>' +
        '<div class="lgkey" style="margin-top:8px">The other chain control levels:</div>' +
        '<div class="rleg">' + others.map(([k, txt]) =>
          '<div class="rrow"><b>' + k + '</b><span>' + txt + '</span></div>')
          .join('') + '</div>';
    } else {
      extra = '<div class="rleg">' + CHAIN_LEVELS.map(([k, txt]) =>
        '<div class="rrow"><b>' + k + '</b><span>' + txt + '</span></div>')
        .join('') + '</div>';
    }
    return v2(ACC.chain, 'Chain control', m.updated ? agoTxt(m.updated) : null,
      esc(norm || m.status || 'Chain control') +
        (m.route ? ' on ' + esc(m.route) : ''),
      esc(m.label || ''),
      [], [], [m.updated ? 'Status set ' + agoTxt(m.updated) : null,
           'Source: Caltrans chain control feed'],
      extra);
  }
  const size = m.acres ? Math.round(m.acres).toLocaleString() + ' acres' : null;
  const cont = (m.contained || m.contained === 0) ? m.contained + '% contained' : null;
  const hasShape = drawablePoly(m.poly);
  return v2(ACC.fire, 'Wildfire', m.discovered ? agoTxt(m.discovered) : null,
    esc((m.name || 'Wildfire')) + ' Fire', null,
    [{ text: hasShape ? 'The outline is the mapped burn footprint.'
        : 'No mapped perimeter yet. The dot marks the reported origin.',
        gloss: true }],
    [size ? ['Size', size] : null, cont ? ['Contained', cont] : null,
     m.discovered ? ['Discovered', agoTxt(m.discovered)] : null],
    ['Source: WFIGS national fire data, with CAL FIRE perimeters']);
}

function pointMarker(m, g) {
  if (g === 'plugin') {
    // A badge: the picture is what it is, the color is whose it is
    // (plugin-badges.js). Official data stays dots.
    const mk = L.marker([m.lat, m.lon], { icon: csPlugin.icon(m), keyboard: false })
      .bindPopup(() => popupFor(m, g), { maxWidth: 320 });
    mk.__m = m; mk.__g = g;
    return mk;
  }
  let style = { renderer: canvasR, radius: 6, color: '#fff', weight: 1.2,
    fillColor: GROUP_DOT[g], fillOpacity: 0.9 };
  if (g.startsWith('clo_') && CLOSURE_STYLES[m.cls]) {
    style = Object.assign({ renderer: canvasR, color: '#fff', weight: 1.2 },
      CLOSURE_STYLES[m.cls]);
  }
  // Lazy popup content: with 10k+ nationwide markers, building HTML
  // strings eagerly on every render is the difference between instant
  // and stuttering on a low-end phone.
  const mk = L.circleMarker([m.lat, m.lon], style)
    .bindPopup(() => popupFor(m, g), { maxWidth: 320 });
  mk.__m = m; mk.__g = g;
  return mk;
}

// Viewport culling: every group's markers live in items[] with only the
// ones near the current view attached to the map. Someone looking at
// California never pays render cost for a dense east-coast state; the
// data itself is still fetched once and never re-queried on pan.
const items = {};
Object.keys(GROUP_DOT).forEach((g) => { items[g] = []; });
// poly ships either as one ring of [lat,lon] pairs (legacy shape) or
// as a MultiPolygon (array of rings); Leaflet renders both, this only
// decides whether there is enough to draw.
const drawablePoly = (poly) => Array.isArray(poly) && poly.length > 0
  && (Array.isArray(poly[0] && poly[0][0]) || poly.length > 2);
function layerForItem(it) {
  if (it.layer) return it.layer;
  const m = it.m;
  if (it.g === 'fire_pt' && drawablePoly(m.poly)) {
    it.layer = L.polygon(m.poly, { color: '#d97706', weight: 2,
      fillColor: '#d97706', fillOpacity: 0.28 })
      .bindPopup(() => popupFor(m, 'fire_pt'), { maxWidth: 320 });
  } else if (it.g === 'sign' && m.blank) {
    it.layer = L.circleMarker([m.lat, m.lon], {
      renderer: canvasR, radius: 5, color: '#fff', weight: 1,
      fillColor: '#b9b3a0', fillOpacity: 0.7,
    }).bindPopup(() => popupFor(m, 'sign'), { maxWidth: 320 });
  } else {
    it.layer = pointMarker(m, it.g);
  }
  // Every layer carries its group so the popup-open refresh deferral
  // recognizes it.
  it.layer.__m = m; it.layer.__g = it.g;
  return it.layer;
}
let lastCullBounds = null;
let cullToken = 0;
function cullSync() {
  cullToken++;
  const view = map.getBounds().pad(0.6);
  for (const g of Object.keys(items)) {
    const grp = ambient[g];
    for (const it of items[g]) {
      const inView = view.contains([it.m.lat, it.m.lon]);
      if (inView && !it.on) { grp.addLayer(layerForItem(it)); it.on = true; }
      else if (!inView && it.on) { grp.removeLayer(it.layer); it.on = false; }
    }
  }
  lastCullBounds = view;
}
// Boot-time variant: attaching 10k+ markers in one synchronous pass
// blocks the first paint on slow hardware. Chunk the attach across
// animation frames and let the pill count REAL progress.
function cullBatched() {
  const mine = ++cullToken;
  const view = map.getBounds().pad(0.6);
  const adds = [];
  for (const g of Object.keys(items)) {
    for (const it of items[g]) {
      const inView = view.contains([it.m.lat, it.m.lon]);
      if (inView && !it.on) adds.push(it);
      else if (!inView && it.on) { ambient[it.g].removeLayer(it.layer); it.on = false; }
    }
  }
  lastCullBounds = view;
  if (adds.length < 3000) {
    for (const it of adds) {
      ambient[it.g].addLayer(layerForItem(it));
      it.on = true;
    }
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    let i = 0;
    const step = () => {
      if (mine !== cullToken) { resolve(); return; }
      const end = Math.min(i + 2500, adds.length);
      for (; i < end; i++) {
        const it = adds[i];
        if (!it.on) {
          ambient[it.g].addLayer(layerForItem(it));
          it.on = true;
        }
      }
      if (!mapDataShown && !mapRefreshPrompt) {
        showPill('Showing ' + i.toLocaleString() + ' of ' +
          adds.length.toLocaleString() + ' reports…');
      }
      if (i < adds.length) requestAnimationFrame(step);
      else resolve();
    };
    requestAnimationFrame(step);
  });
}
let cullTimer = null;
map.on('moveend zoomend', () => {
  clearTimeout(cullTimer);
  // Leaving the last culled area (a big zoom-out, a long pan) means
  // real attach work is coming: say so instead of a frozen beat.
  if (!GL.on && mapDataShown && lastCullBounds
      && !lastCullBounds.contains(map.getBounds())) {
    showPill('Updating the map…');
  }
  cullTimer = setTimeout(() => {
    // One painted frame between showing the pill and the synchronous
    // attach work, so the pill is actually visible during it. GPU
    // mode has no attach work at all.
    requestAnimationFrame(() => {
      if (!GL.on) {
        cullSync();
        if (mapDataShown) hidePill();
      }
      fetchGeometry();
    });
  }, 120);
});


// ── GPU dot rendering (deck.gl, default on; ?gl=0 opts out) ─────────
// Point markers move to one ScatterplotLayer fed by binary typed
// arrays; benchmarked at 4 ms/frame panning versus ~100 ms on the
// canvas renderer, and immune to CPU throttling. Strips, fire
// perimeter polygons, and every popup stay on Leaflet. Requires
// WebGL2 (deck.gl v9); anything without it keeps the canvas path.
const GL = { on: false, deck: null, dirty: false, index: [],
             readyResolvers: [] };
(() => {
  try {
    const qs = new URLSearchParams(location.search);
    if (qs.get('gl') === '0') return;
    const probe = document.createElement('canvas');
    if (!probe.getContext('webgl2')) return;
    GL.on = true;
    // The canvas must live inside a Leaflet pane: the map pane is a
    // CSS stacking context (it gets a transform while panning), so a
    // sibling canvas can only sit above or below ALL panes at once.
    // A pane at z 450 keeps dots over closure strips (400) and under
    // popups (700). The pane is pinned to the viewport every frame
    // because deck.gl already redraws in screen space.
    const pane = map.createPane('glpane');
    pane.style.zIndex = 450;
    pane.style.pointerEvents = 'none';
    const cv = document.createElement('canvas');
    cv.id = 'glcanvas';
    cv.style.cssText = 'position:absolute;inset:0;width:100%;' +
      'height:100%;pointer-events:none';
    const fit = () => {
      const s = map.getSize();
      pane.style.width = s.x + 'px';
      pane.style.height = s.y + 'px';
      L.DomUtil.setPosition(pane, map.containerPointToLayerPoint([0, 0]));
    };
    fit();
    pane.appendChild(cv);
    // Animated zooms (wheel, double-click, +/- buttons) move the tiles
    // with a CSS transition and fire no per-frame events, so without
    // this the dots would sit still and snap at zoomend. Mirror
    // L.Canvas._updateTransform: give the pane the same transition
    // class and the same target transform as the tiles, so the browser
    // animates both in lockstep; the zoomend redraw then lands exactly
    // where the transition ends. (_getNewPixelOrigin is the private
    // helper L.Canvas itself uses; Leaflet is vendored, so it is
    // version-pinned.)
    pane.classList.add('leaflet-zoom-animated');
    map.on('zoomanim', (e) => {
      const scale = map.getZoomScale(e.zoom, map.getZoom());
      const offset = map.getSize().multiplyBy(-0.5 * scale)
        .add(map.project(map.getCenter(), e.zoom))
        .subtract(map._getNewPixelOrigin(e.center, e.zoom));
      L.DomUtil.setTransform(pane, offset, scale);
    });
    const sc = document.createElement('script');
    // The page's preload carries the deploy's version; load that address.
    const pre = document.querySelector('link[rel="preload"][href^="/static/vendor/deck-slim"]');
    sc.src = (pre && pre.getAttribute('href')) || '/static/vendor/deck-slim.min.js';
    sc.onload = () => {
      GL.deck = new deckSlim.Deck({
        canvas: 'glcanvas', controller: false,
        viewState: GL.view(), layers: [] });
      map.on('move zoom zoomend resize', () => {
        fit();
        GL.deck.setProps({ viewState: GL.view() });
      });
      if (GL.dirty) GL.rebuild();
      GL.readyResolvers.forEach((r) => r());
      GL.readyResolvers = [];
    };
    sc.onerror = () => { GL.on = false; cullSync(); };
    document.head.appendChild(sc);
  } catch (e) { GL.on = false; }
})();
GL.view = () => {
  const c = map.getCenter();
  return { longitude: c.lng, latitude: c.lat,
           zoom: map.getZoom() - 1, pitch: 0, bearing: 0 };
};
GL.hex = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16),
                 parseInt(h.slice(5, 7), 16)];
GL.colorFor = (m, g) => {
  if (g.startsWith('clo_') && CLOSURE_STYLES[m.cls]) {
    return GL.hex(CLOSURE_STYLES[m.cls].fillColor);
  }
  if (g === 'sign' && m.blank) return [185, 179, 160];
  return GL.hex(GROUP_DOT[g] || '#787878');
};
GL.whenReady = () => (GL.deck ? Promise.resolve()
  : new Promise((r) => GL.readyResolvers.push(r)));
GL.rebuild = () => {
  if (!GL.on) return Promise.resolve();
  if (!GL.deck) {
    GL.dirty = true;
    return GL.whenReady().then(() => GL.rebuild());
  }
  const checked = {};
  document.querySelectorAll('#filters input[data-group]').forEach(
    (b) => { checked[b.dataset.group] = b.checked; });
  const pts = [];
  for (const g of Object.keys(items)) {
    if (!checked[g]) continue;
    for (const it of items[g]) {
      // Perimeter fires render as Leaflet polygons, not dots.
      if (g === 'fire_pt' && drawablePoly(it.m.poly)) continue;
      // Plugin alerts are badges (cullPlugins), never dots.
      if (g === 'plugin') continue;
      pts.push([it.m, g]);
    }
  }
  const n = pts.length;
  const pos = new Float32Array(n * 2);
  const col = new Uint8Array(n * 4);
  for (let i = 0; i < n; i++) {
    const c = GL.colorFor(pts[i][0], pts[i][1]);
    pos[i * 2] = pts[i][0].lon;
    pos[i * 2 + 1] = pts[i][0].lat;
    col[i * 4] = c[0]; col[i * 4 + 1] = c[1];
    col[i * 4 + 2] = c[2]; col[i * 4 + 3] = 230;
  }
  GL.index = pts;
  if (n && !GL.firstPaint) { GL.firstPaint = true; try { performance.mark('markers-ready'); } catch (e) { /* no marks */ } }
  GL.deck.setProps({ layers: [new deckSlim.ScatterplotLayer({
    id: 'dots',
    data: { length: n, attributes: {
      getPosition: { value: pos, size: 2 },
      getFillColor: { value: col, size: 4 } } },
    radiusUnits: 'pixels', getRadius: 5.5,
    stroked: true, getLineColor: [255, 255, 255, 255],
    lineWidthUnits: 'pixels', getLineWidth: 1,
    pickable: true })] });
  return Promise.resolve();
};
// Fire perimeters still attach as Leaflet polygons in GL mode (145 of
// them; no culling needed).
function cullPolysOnly() {
  for (const it of items.fire_pt) {
    if (!drawablePoly(it.m.poly) || it.on) continue;
    ambient.fire_pt.addLayer(layerForItem(it));
    it.on = true;
  }
}
// Plugin badges also attach as Leaflet markers in GL mode: a view holds
// at most a few hundred, and a badge is an icon, not a dot.
function cullPlugins() {
  let added = 0;
  for (const it of items.plugin) {
    if (it.on) continue;
    ambient.plugin.addLayer(layerForItem(it));
    it.on = true;
    added++;
  }
  if (added && !cullPlugins.marked) { cullPlugins.marked = true; try { performance.mark('plugins-ready'); } catch (e) { /* no marks */ } }
}
// Click picking: the GL canvas never intercepts pointer events, so
// every existing Leaflet interaction is untouched; dot hits resolve
// through deck's GPU picking inside the normal map click.
map.on('click', (e) => {
  if (!GL.on || !GL.deck || pickMode) return;
  const p = map.latLngToContainerPoint(e.latlng);
  const info = GL.deck.pickObject({ x: p.x, y: p.y, radius: 9 });
  if (!info || info.index < 0 || !GL.index[info.index]) return;
  const [m, g] = GL.index[info.index];
  const pop = L.popup({ maxWidth: 320 })
    .setLatLng([m.lat, m.lon])
    .setContent(popupFor(m, g));
  // No fake _source (Leaflet drives real sources through on/off/
  // fire); context rides on the popup object and the enrichers
  // know to look there.
  pop.__m = m; pop.__g = g;
  pop.openOn(map);
});

function rebuildSigns() {
  ambient.sign.clearLayers();
  items.sign = [];
  const withBlank = document.getElementById('signblank').checked;
  let blanks = 0;
  for (const m of signCache) {
    if (m.blank) {
      blanks++;
      if (!withBlank) continue;
    }
    items.sign.push({ m, g: 'sign', layer: null, on: false });
  }
  if (GL.on) GL.rebuild(); else cullSync();
  const el = document.getElementById('n-sign');
  if (el) el.textContent = signCache.length - blanks;
  const bl = document.getElementById('n-signblank');
  if (bl) bl.textContent = blanks;
}

function rebuildCameras() {
  ambient.camera.clearLayers();
  items.camera = [];
  const videoOnly = document.getElementById('camvideo').checked;
  let n = 0;
  for (const m of cameraCache) {
    if (videoOnly && !m.stream) continue;
    items.camera.push({ m, g: 'camera', layer: null, on: false });
    n++;
  }
  if (GL.on) GL.rebuild(); else cullSync();
  const el = document.getElementById('n-camera');
  if (el) el.textContent = n;
  const nv = document.getElementById('n-camvideo');
  if (nv) nv.textContent = cameraCache.filter(c => c.stream).length;
}

let ambientBounds = null, ambientTimer = null, ambientCycle = 0;
const FOCUS_GROUPS = {
  incident: ['inc_collision', 'inc_fire', 'inc_hazard', 'inc_other'],
  closure: ['clo_full', 'clo_lane', 'clo_oneway', 'clo_ramp'],
  chain: ['chain'],
  fire: ['fire_pt'],
};
let focusReq = null;
let focusDone = false;
try {
  const qs = new URLSearchParams(location.search);
  const parts = (qs.get('focus') || '').split(',').map(Number);
  if (parts.length === 2 && parts.every(Number.isFinite)) {
    focusReq = { lat: parts[0], lon: parts[1],
                 kind: qs.get('k') || 'incident' };
  }
} catch (e) { /* no focus */ }

function tryFocus() {
  if (!focusReq || focusDone) return;
  focusDone = true;
  // The focus link is consumed exactly once: clean the URL back to
  // the base so a reload (or a share of the address bar) lands on
  // the normal map instead of chasing an event that may be long gone.
  if (window.history && history.replaceState) {
    history.replaceState(null, '', location.pathname);
  }
  const at = [focusReq.lat, focusReq.lon];
  map.setView(at, Math.max(map.getZoom(), 12));
  // Attach any culled markers around the focus point before searching
  // for the one to open.
  cullSync();
  const ring = L.circleMarker(at, {
    radius: 18, color: '#2f81f7', weight: 3, fill: false,
  }).addTo(map);
  let ringOn = true;
  const pulse = setInterval(() => {
    ringOn = !ringOn;
    ring.setStyle({ opacity: ringOn ? 1 : 0.25 });
  }, 450);
  setTimeout(() => { clearInterval(pulse); map.removeLayer(ring); }, 9000);
  // Open the matching marker's popup when one sits nearby; the event
  // may have cleared since the alert went out, so the ring alone is a
  // valid outcome.
  let best = null;
  for (const g of FOCUS_GROUPS[focusReq.kind] || []) {
    for (const it of items[g] || []) {
      const d = map.distance([it.m.lat, it.m.lon], at);
      if (d < 900 && (!best || d < best.d)) best = { it, g, d };
    }
  }
  if (best) {
    setTimeout(() => {
      if (!GL.on && best.it.layer) { best.it.layer.openPopup(); return; }
      const pop = L.popup({ maxWidth: 320 })
        .setLatLng([best.it.m.lat, best.it.m.lon])
        .setContent(popupFor(best.it.m, best.g));
      pop.__m = best.it.m; pop.__g = best.g;
      pop.openOn(map);
    }, 650);
  } else {
    // The alerted event has cleared since the notification went out:
    // say so instead of leaving a silently empty spot.
    L.popup({ maxWidth: 280 }).setLatLng(at).setContent(
      '<div class="pop"><div class="t">This alert has cleared</div>' +
      '<div class="d">Nothing is being reported at this spot right ' +
      'now. The ring marks where it was.</div></div>').openOn(map);
  }
}

const FAST_GROUPS = ['inc_collision', 'inc_fire', 'inc_hazard', 'inc_other',
  'clo_full', 'clo_lane', 'clo_oneway', 'clo_ramp', 'chain',
  'fire_pt', 'fire_poly', 'toll'];
const HEAVY_GROUPS = ['camera', 'sign', 'rwis'];

// Closure stretch polylines, deferred: built once, the first time the
// zoom crosses STRIP_ZOOM after a data refresh.
let pendingStrips = [];
let stripsBuilt = false;
const STRIP_ZOOM = 8;
// Closure stretch geometry ships separately from the slim boot
// payload (it was 57% of boot bytes and is invisible below
// STRIP_ZOOM). Fetched per 2-degree cell the first time the view
// zooms in, keyed by marker coordinates, kept across data refreshes.
const geoByKey = new Map();
const geoCells = new Map();
const GEO_CELL_TTL = 600000;
const geoKey = (m) => m.lat.toFixed(5) + ',' + m.lon.toFixed(5);
async function fetchGeometry() {
  if (map.getZoom() < STRIP_ZOOM) return;
  const b = map.getBounds().pad(0.3);
  const cells = [];
  for (let la = Math.floor(b.getSouth() / 2) * 2;
       la <= b.getNorth(); la += 2) {
    for (let lo = Math.floor(b.getWest() / 2) * 2;
         lo <= b.getEast(); lo += 2) {
      const key = la + '_' + lo;
      const ts = geoCells.get(key);
      if (!ts || Date.now() - ts > GEO_CELL_TTL) cells.push([key, la, lo]);
    }
  }
  if (!cells.length) return;
  cells.forEach(([k]) => geoCells.set(k, Date.now()));
  await Promise.all(cells.map(async ([k, la, lo]) => {
    try {
      const res = await fetch('/api/mapdata?bbox=' + la + ',' + lo + ',' +
        (la + 2) + ',' + (lo + 2) + '&kinds=closure,toll&fields=geo',
        { cache: 'no-cache' });
      if (!res.ok) { geoCells.delete(k); return; }
      const d = await res.json();
      for (const m of d.markers || []) {
        if (m.kind === 'toll') geoByKey.set('t' + geoKey(m), m.segs);
        else geoByKey.set(geoKey(m), m.path);
      }
    } catch (e) { geoCells.delete(k); }
  }));
  stripsBuilt = false;
  syncStrips();
}

// One click, everything on that stretch: collect every line layer
// within tolerance of the click and stack their popups in a single
// window, urgent things (closures) first, the toll context last. No
// more guessing which of two overlapping lines a click will hit.
function lineHitsAt(containerPt) {
  const hits = [];
  const groups = Object.keys(ambient).filter((g) =>
    (g.startsWith('clo_') || g === 'toll') && map.hasLayer(ambient[g]));
  for (const g of groups) {
    ambient[g].eachLayer((l) => {
      if (!(l instanceof L.Polyline) || l instanceof L.Polygon) return;
      const parts0 = l.getLatLngs();
      const parts = Array.isArray(parts0[0]) ? parts0 : [parts0];
      let best = Infinity;
      for (const part of parts) {
        for (let i = 1; i < part.length; i++) {
          const a = map.latLngToContainerPoint(part[i - 1]);
          const b = map.latLngToContainerPoint(part[i]);
          const d = L.LineUtil.pointToSegmentDistance(containerPt, a, b);
          if (d < best) best = d;
        }
      }
      if (best <= (l.options.weight || 4) / 2 + 7) {
        hits.push({ g, m: l.__m, d: best });
      }
    });
  }
  hits.sort((x, y) => (x.g === 'toll') - (y.g === 'toll') || x.d - y.d);
  return hits;
}
function openStacked(latlng) {
  const hits = lineHitsAt(map.latLngToContainerPoint(latlng));
  if (!hits.length) return false;
  // Toll details go to the left-hand panel, never a popup: a popup on
  // the road covered the very corridor the rate rows highlight. The
  // popup (if any) opens FIRST so its popupopen does not dismiss the
  // panel opened by this same click.
  const toll = hits.find((h) => h.g === 'toll');
  const rest = hits.filter((h) => h.g !== 'toll');
  if (rest.length) {
    const seen = new Set();
    const parts = [];
    for (const h of rest) {
      if (seen.has(h.m)) continue;
      seen.add(h.m);
      if (parts.length >= 3) {
        parts.push('<div class="pop"><div class="d">and ' +
          (seen.size - parts.length) + ' more on this stretch</div></div>');
        break;
      }
      parts.push(popupFor(h.m, h.g));
    }
    const pop = L.popup({ maxWidth: 330 }).setLatLng(latlng)
      .setContent(parts.join('<div class="stackdiv"></div>'));
    // Tag the popup BEFORE opening: popupopen listeners run inside
    // openOn, and tagging after the fact is how the old hover
    // highlighting silently broke.
    pop.__m = rest[0].m;
    pop.__g = rest[0].g;
    pop.openOn(map);
  }
  if (toll) openTollPanel(toll.m);
  return true;
}
// ---- toll details: the right-hand details pane, like every other kind ----
// Hovering a rate row lights up that stretch of the corridor (wired in
// openInspector). Closing the pane, a bare map click, any popup, or
// Escape clears the highlight.
function closeTollPanel() { tollHiClear(); }
function openTollPanel(m) { openInspector(m, 'toll'); }
map.on('click', closeTollPanel);
map.on('popupopen', closeTollPanel);
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeTollPanel();
});
function tollRangeText(m) {
  const money = (v) => '$' + v.toFixed(2).replace(/\.00$/, '');
  const range = m.min === m.max ? money(m.min)
    : money(m.min) + '–' + money(m.max);
  return range + (m.pricing === 'live' ? ' now' : '')
    + ', ' + (m.toll_type === 'required' ? 'toll road' : 'express lane');
}
// Price tags and direction arrows live in their own group inside the
// toll group, so they can be rebuilt on every zoom (both are placed in
// screen space) without disturbing the corridor lines, and the layer
// checkbox still hides everything at once.
const tollLabels = L.layerGroup();
function tollMoney(v) {
  return '$' + Number(v).toFixed(2).replace(/\.00$/, '');
}
// Greedy declutter: a tag is kept only when it is far enough on screen
// from every tag already placed, so dense interchanges thin out
// instead of stacking into an unreadable pile.
function syncTollLabels() {
  tollLabels.clearLayers();
  if (!map.hasLayer(ambient.toll) || map.getZoom() < STRIP_ZOOM) return;
  const view = map.getBounds().pad(0.2);
  const placed = [];
  for (const [m, g] of pendingStrips) {
    if (g !== 'toll') continue;
    const segs = (Array.isArray(m.segs) && m.segs.length)
      ? m.segs : geoByKey.get('t' + geoKey(m));
    if (!Array.isArray(segs) || !segs.length) continue;
    // Direction arrows: chevrons along the deck pointing the way the
    // toll is charged. Only for one-way tolls (the bridges), where
    // assuming both directions pay would be an expensive mistake.
    if (m.toll_dir && map.getZoom() >= 11) {
      const flat = segs.flat();
      for (let f = 0.2; f < 0.95; f += 0.3) {
        const i = Math.max(1, Math.round(f * (flat.length - 1)));
        const a = map.latLngToContainerPoint(flat[i - 1]);
        const b = map.latLngToContainerPoint(flat[i]);
        const len = Math.hypot(b.x - a.x, b.y - a.y) || 1;
        const ux = (b.x - a.x) / len, uy = (b.y - a.y) / len;
        const size = 9;
        const tip = L.point(b.x, b.y);
        const back = L.point(tip.x - ux * size, tip.y - uy * size);
        const wing = size * 0.55;
        const p1 = L.point(back.x - uy * wing, back.y + ux * wing);
        const p2 = L.point(back.x + uy * wing, back.y - ux * wing);
        tollLabels.addLayer(L.polyline([
          map.containerPointToLatLng(p1), map.containerPointToLatLng(tip),
          map.containerPointToLatLng(p2),
        ], { renderer: canvasR, color: '#334155', weight: 2.5,
             opacity: 0.95, interactive: false }));
      }
    }
    for (const e of (m.entries || [])) {
      const at = (e.pts || [])[0];
      const row = (e.rows || [])[0];
      if (!at || !row || row[1] == null) continue;
      if (!view.contains(at)) continue;
      const p = map.latLngToContainerPoint(at);
      if (placed.some((q) => Math.abs(q.x - p.x) < 60
                          && Math.abs(q.y - p.y) < 36)) continue;
      placed.push(p);
      tollLabels.addLayer(L.marker(at, { interactive: false,
        icon: L.divIcon({ className: '', iconSize: null,
          html: '<div class="ttag"><div class="tb">' + tollMoney(row[1]) +
                '</div><div class="ts"></div><div class="td"></div></div>' }) }));
    }
  }
}
function syncStrips() {
  if (stripsBuilt || map.getZoom() < STRIP_ZOOM) return;
  stripsBuilt = true;
  if (!ambient.toll.hasLayer(tollLabels)) ambient.toll.addLayer(tollLabels);
  for (const [m, g] of pendingStrips) {
    if (g === 'toll') {
      const segs = (Array.isArray(m.segs) && m.segs.length)
        ? m.segs : geoByKey.get('t' + geoKey(m));
      if (!Array.isArray(segs) || !segs.length) continue;
      // A quiet slate line that never competes with a red closure or
      // an orange incident on the same road: the PRICES do the
      // talking, on tags pinned to each gantry (syncTollLabels). The
      // line colour carries no status meaning to misread.
      const line = L.polyline(segs, {
        renderer: canvasR, color: '#64748b', weight: 4.5, opacity: 0.55,
      }).on('click', (e) => { openStacked(e.latlng); L.DomEvent.stop(e); })
        .bindTooltip(tollRangeText(m), { sticky: true });
      line.__m = m; line.__g = g;
      ambient[g].addLayer(line);
      // Closure and incident geometry wins clicks where they overlap
      // a toll corridor; the corridor stays reachable a few pixels
      // to either side.
      line.bringToBack();
      continue;
    }
    // Real road geometry ONLY. A straight begin-to-end segment cuts
    // corners on any curved road, so closures without geometry stay
    // dots. Some feeds dress a straight line as a 2-point LineString
    // (UDOT's WZDx): those only draw when short enough that straight
    // IS the road. Geometry comes from the marker itself (native
    // full-payload mode) or the lazily fetched geometry store.
    const path = (Array.isArray(m.path) && m.path.length > 1)
      ? m.path : geoByKey.get(geoKey(m));
    if (!Array.isArray(path) || path.length < 2) continue;
    if (path.length === 2
        && map.distance(path[0], path[1]) > 800) continue;
    const strip = L.polyline(path, {
      renderer: canvasR, color: GROUP_DOT[g], weight: 4, opacity: 0.45,
    }).on('click', (e) => { openStacked(e.latlng); L.DomEvent.stop(e); });
    strip.__m = m; strip.__g = g;
    ambient[g].addLayer(strip);
  }
}
map.on('zoomend', syncStrips);
// Tags and arrows are positioned in screen space, so they follow every
// pan and zoom rather than being built once.
map.on('zoomend moveend', syncTollLabels);

// Refreshing a group rebuilds its layers, which CLOSES any popup a
// user is reading (reported as "clicking the dispatch log took me away
// from the incident": the 3-minute refresh landed mid-read). Defer the
// rebuild until the popup closes; road data can be 3 minutes stale
// while someone reads, a vanishing popup cannot.
let pendingBatches = [];
map.on('popupclose', () => {
  if (!pendingBatches.length) return;
  const todo = pendingBatches;
  pendingBatches = [];
  // Let the close finish before rebuilding (same-tick rebuild can
  // re-trigger popup bookkeeping).
  setTimeout(() => todo.forEach(([m, g]) => renderBatch(m, g)), 80);
});
function popupBlocksRefresh(groups) {
  if (!map._popup || !map._popup.isOpen()) return false;
  const src = map._popup.__g ? map._popup : map._popup._source;
  return !!(src && src.__g && groups.includes(src.__g));
}

function renderBatch(markers, groups) {
  if (popupBlocksRefresh(groups)) {
    pendingBatches = pendingBatches.filter(([, g]) =>
      g.join() !== groups.join());
    pendingBatches.push([markers, groups]);
    return;
  }
  const counts = {};
  for (const g of groups) { ambient[g].clearLayers(); items[g] = []; }
  if (groups.includes('camera')) { cameraCache = []; signCache = []; }
  if (groups.some((g) => g.startsWith('clo_') || g === 'toll')) {
    pendingStrips = [];
  }
  for (const m of markers) {
    const g = classify(m);
    if (!g || !m.lat || !groups.includes(g)) continue;
    if (g === 'camera') { cameraCache.push(m); continue; }
    if (g === 'sign') { signCache.push(m); continue; }
    counts[g] = (counts[g] || 0) + 1;
    // Every closure is a strip candidate: its road geometry either
    // rode along (native feeds) or arrives lazily from the geometry
    // endpoint once the user zooms past STRIP_ZOOM. syncStrips only
    // draws real geometry either way. Fire perimeter polygons and
    // blank signs shape via layerForItem.
    if (g.startsWith('clo_') || g === 'toll') {
      pendingStrips.push([m, g]);
    }
    // Tolls are lines-only: no dot in the point registries, so they
    // can never be confused with incident or closure dots.
    if (g === 'toll') continue;
    if (g === 'plugin') continue;   // drawn by applyPlugins, by difference
    items[g].push({ m, g, layer: null, on: false });
  }
  stripsBuilt = false;
  syncStrips();
  syncTollLabels();
  const attach = GL.on
    ? (cullPolysOnly(), cullPlugins(), GL.rebuild())
    : mapDataShown ? (cullSync(), Promise.resolve())
    : cullBatched();
  if (groups.includes('camera')) { rebuildCameras(); rebuildSigns(); }
  if (groups.includes('inc_collision')) tryFocus();
  for (const g of groups) {
    if (g === 'camera' || g === 'sign') continue;
    const el = document.getElementById('n-' + g);
    if (el) el.textContent = counts[g] || 0;
  }
  return attach;
}

// Loading pill: visible from page load until the first batch of dots
// lands, with honest escalation text on slow loads and an automatic
// backoff retry on failure (previously a failed first fetch left a
// silently empty map for up to 3 minutes until the interval refresh).
const mapLoadingEl = document.getElementById('maploading');
const mapLoadingText = document.getElementById('maploadingtext');
let mapDataShown = false;
let mapRetryDelay = 4000;
// The pill is reusable: first data load, failed-fetch retries, and the
// re-attach work when a zoom-out pulls thousands of culled markers
// back onto the canvas all share it.
function showPill(text) {
  mapLoadingEl.classList.remove('gone');
  mapLoadingText.textContent = text;
}
function hidePill() { mapLoadingEl.classList.add('gone'); }
// Coverage: the map only holds the region it last fetched. Panning or
// zooming past that edge means the view is showing SOME of what is
// out there, not all of it, and the page says so with a live count
// until the wider fetch lands.
let coveragePill = false;
function viewCovered() {
  return !!(ambientBounds && ambientBounds.contains(map.getBounds()));
}
function coverageStatus(total, pct) {
  const have = GL.on ? GL.index.length
    : Object.keys(items).reduce((n, g) => n + items[g].length, 0);
  if (total > 0) {
    return 'Loading this area: ' + have.toLocaleString() + ' of ' +
      total.toLocaleString() + ' reports' + (pct != null ? ' (' + pct + '%)' : '…');
  }
  return 'Loading more reports for this area…';
}
function showCoveragePill(total, pct) {
  if (!mapDataShown || mapRefreshPrompt || warmPill) return;
  coveragePill = true;
  showPill(coverageStatus(total, pct));
}
function clearCoveragePill() {
  if (!coveragePill) return;
  coveragePill = false;
  if (!warmPill) hidePill();
}
function mapLoadingDone() {
  if (!mapDataShown) {
    mapDataShown = true;
    mapLoadingEl.classList.remove('clickable');
    // Data made it: a refresh prompt shown during a slow first
    // response is obsolete and must not suppress later pill text.
    mapRefreshPrompt = false;
  }
  // While the warm-up counter owns the pill, refreshes must not blink
  // it off between polls; the warm loop hides it at completion.
  if (!warmPill) hidePill();
}
// After 5 seconds WITHOUT progress the pill turns into a clickable
// refresh prompt; a reload restarts the preload fetch, which is the
// fastest recovery when the first request got a bad instance. While
// bytes are arriving or the server is reporting warm-up progress the
// prompt stays away: reloading a page that is visibly working only
// restarts the wait.
let mapRefreshPrompt = false;
let lastLoadProgress = Date.now();
(function armRefreshPrompt() {
  setTimeout(() => {
    if (mapDataShown) return;
    if (Date.now() - lastLoadProgress < 4500) { armRefreshPrompt(); return; }
    mapRefreshPrompt = true;
    mapLoadingText.textContent = 'Still loading? Try refreshing the page';
    mapLoadingEl.classList.add('clickable');
    mapLoadingEl.addEventListener('click', () => location.reload());
  }, 5000);
})();
// Warm-up loop: a fresh server instance answers the boot request with
// whatever feeds are already cached plus X-Warm-Ready/Total counters;
// the page keeps re-polling (and showing "X of Y") until every state
// feed has reported in.
let warmReady = -1, warmTotal = 0, warmTimer = null, warmPill = false;
let warmPolls = 0;
let bootBytes = false;
let incomingCount = 0;
// Before the first map response has produced a single byte there is no
// download percentage to show, so poll the instant warm-up endpoint:
// its climbing "X of Y feeds" counter is real progress (it also keeps
// the refresh prompt away while the server is visibly working).
(function pollWarmup(n) {
  if (mapDataShown || bootBytes || n > 40) return;
  fetch('/api/warmup').then(r => r.json()).then(w => {
    if (mapDataShown || bootBytes || !w.total) return;
    if (w.ready > warmReady) lastLoadProgress = Date.now();
    warmReady = w.ready; warmTotal = w.total;
    if (!mapRefreshPrompt && w.ready < w.total) {
      showPill('Starting up: ' + w.ready + ' of ' + w.total +
        ' feeds ready…');
    }
    if (w.ready < w.total) setTimeout(() => pollWarmup(n + 1), 1500);
  }).catch(() => {});
})(0);


// ── Snapshot boot ───────────────────────────────────────────────────
// The map no longer boots through the API. A publisher builds one
// coverage-wide object per bundle and uploads it pre-gzipped to GCS
// behind Cloudflare, so first paint is an edge-cached static file: no
// cold instance, no feed warming and no per-request gzip sitting in the
// boot path. /api/mapdata still serves the assistant, routing, watch
// areas and the fields=geo lazy geometry.
//
// If the snapshot host is unreachable the same payload is fetched from
// /api/mapdata instead, so a bad day degrades to the old behaviour
// rather than to a blank map.
const SNAP_BASE = 'https://data.commutescout.com';
const SNAP_BUNDLES = {
  live: { file: 'live.json.gz', kinds: 'incident,closure,chain,fire,toll,plugin' },
  cameras: { file: 'cameras.json.gz', kinds: 'camera' },
  signs: { file: 'signs.json.gz', kinds: 'sign,rwis' },
};
// One object holds every marker we publish, so panning never needs
// another fetch and the containment check always passes. Filtering to
// the viewport is the client's job and already runs (cullSync).
const SNAP_BOUNDS = L.latLngBounds([[-85, -180], [85, 180]]);
let snapSchema = null;
let snapPublished = 0;        // ms epoch of the freshest payload held
let snapReloadArmed = false;

// "Data as of" is the kiosk's health indicator. Fresh data keeps it
// quiet; a stalled publisher or a dead network makes it visibly age
// instead of the map silently freezing on hours-old dots.
function paintAsOf() {
  const el = document.getElementById('asof');
  if (!el || !snapPublished) return;
  const mins = Math.floor((Date.now() - snapPublished) / 60000);
  const t = new Date(snapPublished).toLocaleTimeString([],
    { hour: 'numeric', minute: '2-digit' });
  el.hidden = false;
  el.classList.toggle('stale', mins >= 2 && mins < 15);
  el.classList.toggle('old', mins >= 15);
  const ago = mins < 60 ? mins + ' min ago'
    : Math.floor(mins / 60) + ' hr ago';
  el.textContent = 'Data as of ' + t + (mins >= 2 ? ' (' + ago + ')' : '');
}
setInterval(paintAsOf, 30000);

// A tab open on a wall monitor outlives deploys. Rather than break on a
// payload it no longer understands, it reloads itself once the map is
// idle: never mid-popup, so it cannot yank something out from under a
// person standing at the screen.
function checkSchema(p) {
  if (!p || !p.schema) return;
  if (snapSchema === null) { snapSchema = p.schema; return; }
  if (p.schema === snapSchema || snapReloadArmed) return;
  snapReloadArmed = true;
  const go = () => {
    if (document.querySelector('.leaflet-popup')) { setTimeout(go, 60000); }
    else { location.reload(); }
  };
  setTimeout(go, 5000);
}

// The service worker keeps the last snapshot on disk. Reading it here
// paints a repeat visit with zero network in the critical path; the
// network copy replaces it a moment later. Anything old enough to
// matter is labelled by the "data as of" chip.
async function cachedBundle(key) {
  if (!('caches' in window)) return null;
  try {
    const hit = await caches.match(SNAP_BASE + '/' + SNAP_BUNDLES[key].file);
    return hit ? await hit.json() : null;
  } catch (e) { return null; }
}

async function fetchBundle(key) {
  const b = SNAP_BUNDLES[key];
  try {
    const res = await fetch(SNAP_BASE + '/' + b.file, { cache: 'no-cache' });
    if (res.ok) return await res.json();
  } catch (e) { /* snapshot host unreachable: fall back below */ }
  try {
    const res = await fetch('/api/mapdata?bbox=-85,-180,85,180&kinds=' +
      b.kinds + '&slim=1', { cache: 'no-cache' });
    if (!res.ok) return null;
    return await res.json();
  } catch (e) { return null; }
}

async function refreshAmbient(force) {
  if (!force && ambientBounds && ambientBounds.contains(map.getBounds())) {
    return;
  }
  const mine = ++ambientCycle;
  const note = (p) => {
    if (!p) return;
    checkSchema(p);
    const t = p.published ? Date.parse(p.published) : 0;
    if (t && t > snapPublished) { snapPublished = t; paintAsOf(); }
  };
  const fast = (async () => {
    // Boot only: paint whatever is already on disk, then let the
    // network copy replace it. Repeat visits show a full map before a
    // single byte moves.
    if (ambientBounds === null) {
      const cached = await cachedBundle('live');
      if (cached && mine === ambientCycle) {
        note(cached);
        const first = renderBatch(cached.markers || [], FAST_GROUPS);
        if (first && first.then) await first;
        mapLoadingDone();
      }
    }
    const p = await fetchBundle('live');
    if (mine !== ambientCycle || !p) return false;
    note(p);
    lastLoadProgress = Date.now();
    const done = renderBatch(p.markers || [], FAST_GROUPS);
    if (done && done.then) await done;
    mapLoadingDone();
    return true;
  })();
  // Cameras and signs land in ONE renderBatch: it clears the camera and
  // sign caches together, so rendering them separately would wipe the
  // other's markers.
  const heavy = (async () => {
    const [cams, signs] = await Promise.all([
      fetchBundle('cameras'), fetchBundle('signs')]);
    if (mine !== ambientCycle) return true;
    if (!cams && !signs) return false;
    [cams, signs].forEach(note);
    renderBatch([...((cams || {}).markers || []),
      ...((signs || {}).markers || [])], HEAVY_GROUPS);
    return true;
  })();
  const [fastOk, heavyOk] = await Promise.all([fast, heavy]);
  if (mine !== ambientCycle) return;
  if (fastOk && heavyOk) {
    ambientBounds = SNAP_BOUNDS;
    mapRetryDelay = 4000;
    clearCoveragePill();
  } else if (!mapDataShown) {
    // The page is useless without the first batch: keep retrying with
    // backoff instead of sitting blank until the interval refresh.
    if (!mapRefreshPrompt) {
      mapLoadingText.textContent = 'Connection hiccup - retrying…';
    }
    setTimeout(() => refreshAmbient(true), mapRetryDelay);
    mapRetryDelay = Math.min(mapRetryDelay * 2, 30000);
  }
}
map.on('moveend zoomend', () => {
  clearTimeout(ambientTimer);
  // The debounce keeps the fetch from firing mid-gesture, but when
  // the view has left the loaded region the user is staring at an
  // incomplete map. Measured on production, that 450ms wait was three
  // quarters of an entire warm refetch (22ms to first byte, 120ms to
  // download, 2ms to render), so uncovered views get a short fuse.
  const covered = viewCovered();
  ambientTimer = setTimeout(() => refreshAmbient(false), covered ? 450 : 120);
  // Say it the instant the view leaves the loaded region, not when
  // the debounced fetch finally starts: the user is looking at a
  // partial picture right now and deserves to know. No denominator
  // yet - the previous fetch counted a different region, and
  // inventing a number here would be a lie. The real total arrives
  // with the next response head a moment later.
  if (mapDataShown && !covered) showCoveragePill(0, null);
});
refreshAmbient(true);

// ── Plugins in the Layers list ──────────────────────────────────────
// One row per plugin under the master switch: its badge, its name, how
// many of its alerts are in view, and a switch. The switch is the same
// one the marketplace's Install button flips (cs.plugins.off), so the
// two can never disagree.
const pluginListEl = document.getElementById('pluginlist');
const pluginRows = new Map();   // id -> { name, kinds, count }
function pluginSeen(markers) {
  for (const m of markers) {
    const sid = csPlugin.sourceId(m);
    if (!pluginRows.has(sid)) pluginRows.set(sid, { name: m.source || sid, kinds: null, count: 0 });
  }
}
function drawPluginList() {
  if (!pluginListEl) return;
  const off = pluginSwitches().off;
  pluginListEl.innerHTML = [...pluginRows.entries()].map(([sid, row]) =>
    '<label class="subopt plug"><input type="checkbox" data-plugin="' + esc(sid) + '"' +
    (off.includes(sid) ? '' : ' checked') + '>' +
    csPlugin.badge(sid, row.kinds ? csPlugin.kindFor(row.kinds) : null, 'sm') +
    '<span>' + esc(row.name) + '</span> <em>' + (row.count || '') + '</em></label>').join('');
}
if (pluginListEl) {
  pluginListEl.addEventListener('change', (e) => {
    const sid = e.target && e.target.dataset.plugin;
    if (!sid) return;
    const sw = pluginSwitches();
    const off = sw.off.filter((x) => x !== sid);
    if (!e.target.checked) off.push(sid);
    try { localStorage.setItem('cs.plugins.off', off.join(',')); } catch (err) { /* private mode */ }
    applyPlugins();
  });
  fetch('/api/flare/sources', { headers: { Accept: 'application/json' } })
    .then((r) => (r.ok ? r.json() : { sources: [] }))
    .then((d) => {
      for (const s of d.sources || []) {
        const row = pluginRows.get(s.id) || { count: 0 };
        pluginRows.set(s.id, { name: s.name || s.id, kinds: s.kinds || null, count: row.count });
      }
      drawPluginList();
    }).catch(() => { /* the list fills from the alerts themselves */ });
}

// ── Plugin alerts ───────────────────────────────────────────────────
// Two kinds of plugin, fetched two ways, drawn as one layer that is
// never cleared and redrawn: markers are added and removed by id, so a
// pan or a zoom moves what is there and nothing blinks.
//
// Shared plugins (fixed cameras: the same for everyone, nobody's
// position in them) are fetched once for the whole country and again
// every so often. Community plugins are served in a small circle
// around whoever is asking and to nobody else, because an alert exists
// because somebody was standing somewhere; those are fetched for a
// place-sized view, and what was fetched stays on the map while the
// view widens, until it expires.
const SHARED_REFRESH_MS = 15 * 60 * 1000;
const COMMUNITY_KEEP_MS = 20 * 60 * 1000;
const sharedAlerts = new Map();      // id -> marker
const communityAlerts = new Map();   // id -> { m, at }
let sharedAt = 0;
let pluginTimer = null;
let pluginCycle = 0;
let lastPluginBox = null;

function pluginMarkerStale(m, at, now) {
  if (now - at > COMMUNITY_KEEP_MS) return true;
  const t = Date.parse(m.confirmed || m.reported || '');
  return Number.isFinite(t) && m.ttl_s && now - t > m.ttl_s * 1000;
}

// The plugin layer, brought to the wanted set: add what is new, drop
// what is gone, touch nothing else. A marker whose popup is open stays
// until it closes.
function applyPlugins() {
  const now = Date.now();
  const want = new Map();
  for (const m of sharedAlerts.values()) if (!pluginHidden(m)) want.set(m.id, m);
  for (const [id, rec] of communityAlerts) {
    if (pluginMarkerStale(rec.m, rec.at, now)) { communityAlerts.delete(id); continue; }
    if (!pluginHidden(rec.m)) want.set(id, rec.m);
  }
  const open = (map._popup && map._popup.isOpen()) ? (map._popup.__m || (map._popup._source || {}).__m) : null;
  const have = new Map(items.plugin.map((it) => [it.m.id, it]));
  for (const [id, it] of have) {
    if (want.has(id) || (open && open.id === id)) continue;
    if (it.layer && it.on) ambient.plugin.removeLayer(it.layer);
    have.delete(id);
  }
  for (const [id, m] of want) {
    if (have.has(id)) continue;
    const it = { m, g: 'plugin', layer: null, on: false };
    have.set(id, it);
  }
  items.plugin = [...have.values()];
  cullPlugins();
  if (!GL.on) cullSync();
  const el = document.getElementById('n-plugin');
  if (el) el.textContent = items.plugin.length;
  const counts = new Map();
  for (const it of items.plugin) {
    const sid = csPlugin.sourceId(it.m);
    counts.set(sid, (counts.get(sid) || 0) + 1);
  }
  for (const [sid, row] of pluginRows) row.count = counts.get(sid) || 0;
  drawPluginList();
  scheduleAlerts();
}

async function fetchPluginBox(bbox) {
  const res = await fetch('/api/mapdata?bbox=' + bbox + '&kinds=plugin&slim=1', { cache: 'no-cache' });
  if (!res.ok) return null;
  return (await res.json()).markers || [];
}

async function refreshPlugins() {
  const mine = ++pluginCycle;
  const now = Date.now();
  try {
    if (now - sharedAt > SHARED_REFRESH_MS) {
      // Every shared plugin at once: the server gives a region-wide view
      // only what is the same for everyone.
      const all = await fetchPluginBox('17,-170,72,-65');
      if (all && mine === pluginCycle) {
        sharedAlerts.clear();
        for (const m of all) { pluginSeen([m]); sharedAlerts.set(m.id, m); }
        sharedAt = Date.now();
      }
    }
    const b = map.getBounds();
    const span = Math.max(b.getNorth() - b.getSouth(), b.getEast() - b.getWest());
    // The server's VIEW_MAX_DEG: wider than this is a region, and the
    // community plugins are not asked.
    if (span <= 4.0) {
      const bbox = [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
        .map((v) => v.toFixed(3)).join(',');
      if (bbox !== lastPluginBox || now - (communityAlerts.at || 0) > 60000) {
        const got = await fetchPluginBox(bbox);
        if (got && mine === pluginCycle) {
          lastPluginBox = bbox;
          communityAlerts.at = Date.now();
          for (const m of got) {
            if (sharedAlerts.has(m.id)) continue;
            pluginSeen([m]);
            communityAlerts.set(m.id, { m, at: communityAlerts.at });
          }
        }
      }
    }
  } catch (e) { /* the next view or the next tick tries again */ }
  if (mine === pluginCycle) applyPlugins();
}
map.on('moveend zoomend', () => {
  clearTimeout(pluginTimer);
  pluginTimer = setTimeout(refreshPlugins, 300);
});
// Full badges where there is room for them, small ones at city-region
// zoom, colored specks beyond that.
function badgeScale() {
  const z = map.getZoom();
  const el = map.getContainer();
  el.classList.toggle('pz-mid', z < 12 && z >= 9);
  el.classList.toggle('pz-low', z < 9);
}
map.on('zoomend', badgeScale);
badgeScale();
refreshPlugins();

// ── Long-running sessions (wall monitor / kiosk) ─────────────────────
// 30 s, not 180 s: the snapshot carries a strong ETag, so an idle open
// map costs a 304 and a few bytes per poll. This is what sets on-screen
// freshness for a display nobody ever touches.
setInterval(() => { refreshAmbient(true); refreshPlugins(); }, 30000);
// Browsers throttle timers in hidden tabs, and a monitor that sleeps
// overnight would otherwise show yesterday's dots until the next tick.
// Catch up the moment the tab is visible again or the network returns.
let lastWake = 0;
function catchUp() {
  if (document.visibilityState === 'hidden') return;
  // Two events often fire together on wake; one refresh is enough.
  if (Date.now() - lastWake < 3000) return;
  lastWake = Date.now();
  paintAsOf();
  refreshAmbient(true);
}
document.addEventListener('visibilitychange', catchUp);
window.addEventListener('online', catchUp);
window.addEventListener('pageshow', (e) => { if (e.persisted) catchUp(); });

document.querySelectorAll('#filters input[data-group]').forEach(box => {
  box.addEventListener('change', () => {
    const layer = ambient[box.dataset.group];
    if (box.checked) map.addLayer(layer); else map.removeLayer(layer);
    // Turning tolls on should not wait for the next idle geometry
    // pass: fetch and build the corridor lines immediately. Then
    // push every toll line to the back of the canvas hit order:
    // bringToBack is a no-op while the group is off the map, so
    // without this, toll dashes added on toggle sat on TOP and
    // swallowed clicks meant for closure lines beneath them.
    if (box.dataset.group === 'toll') {
      if (box.checked) {
        stripsBuilt = false;
        fetchGeometry();
        syncStrips();
        ambient.toll.eachLayer((l) => { if (l.bringToBack) l.bringToBack(); });
      }
      syncTollLabels();
    }
    GL.rebuild();
  });
});
document.getElementById('allnone').addEventListener('click', () => {
  const boxes = [...document.querySelectorAll('#filters input[data-group]')];
  const turnOn = boxes.some((b) => !b.checked);
  for (const b of boxes) {
    if (b.checked !== turnOn) {
      b.checked = turnOn;
      b.dispatchEvent(new Event('change'));
    }
  }
});

// Official sources, plugins, or both: three buttons over the same
// checkboxes below, so there is still one switch per layer. Leaving
// "Everything" remembers what was on; coming back restores it.
(function sourceFilter() {
  const el = document.getElementById('srcfilter');
  if (!el) return;
  const boxes = () => [...document.querySelectorAll('#filters input[data-group]')];
  let saved = null;
  function set(box, on) {
    if (box.checked === on) return;
    box.checked = on;
    box.dispatchEvent(new Event('change'));
  }
  el.addEventListener('change', (e) => {
    const mode = e.target && e.target.value;
    if (!mode) return;
    if (!saved) saved = new Map(boxes().map((b) => [b.dataset.group, b.checked]));
    for (const b of boxes()) {
      const plugin = b.dataset.group === 'plugin';
      if (mode === 'all') set(b, saved.get(b.dataset.group));
      else if (mode === 'official') set(b, plugin ? false : saved.get(b.dataset.group));
      else set(b, plugin);
    }
    if (mode === 'all') saved = null;
  });
})();

// States without coverage yet get a gray outline that says so.
const COVERED = new Set(['California', 'Nevada', 'Maine', 'New Hampshire',
  'Vermont', 'Iowa', 'North Carolina', 'Washington', 'Oregon', 'Ohio',
  'Utah', 'Arizona', 'Idaho', 'Wisconsin', 'New York', 'Indiana',
  'Minnesota', 'Kansas', 'New Jersey', 'Maryland', 'Missouri',
  'Illinois', 'Kentucky', 'Oklahoma', 'Hawaii', 'Louisiana',
  'Delaware', 'Michigan', 'Tennessee', 'Mississippi', 'Alaska',
  'Colorado', 'Florida', 'Virginia', 'Connecticut']);
// rIC takes an options dict, not a delay: passing a number throws a
// synchronous TypeError in Chromium and kills every handler below.
const idle = (cb) => window.requestIdleCallback
  ? requestIdleCallback(cb, { timeout: 1500 }) : setTimeout(cb, 1200);
// Partial-coverage states have real data but not the default layers,
// so they get an outline and an honest note instead of a gray wash.
const PARTIAL = {
  Alabama: 'live traffic cameras (turn on the Cameras layer and zoom '
    + 'in). Incident and closure feeds need ALDOT credentials and are '
    + 'in progress.',
  Texas: 'Austin-area roadwork from the City of Austin open data feed. '
    + 'Statewide TxDOT data has licensing terms that block reuse here.',
};
// Filled by the loader below; drives the map-click hit test.
let nocovFeatures = [];
idle(async () => {
  try {
    const res = await fetch('/static/us-states.json');
    if (!res.ok) return;
    const geo = await res.json();
    // The wash lives in a pane UNDER the marker canvas so nationwide
    // dots (wildfires, alerts) render crisply above it and stay
    // clickable. That pane never receives clicks itself, so the
    // coverage popups are opened by the map-click hit test below.
    map.createPane('nocov');
    map.getPane('nocov').style.zIndex = 250;
    const missing = { type: 'FeatureCollection',
      features: geo.features.filter((f) => !COVERED.has(f.properties.NAME)
        && !PARTIAL[f.properties.NAME]) };
    L.geoJSON(missing, {
      pane: 'nocov', interactive: false,
      style: { color: '#8b98a7', weight: 1, dashArray: '4 5',
        fillColor: '#8b98a7', fillOpacity: 0.07 },
    }).addTo(map);
    const partial = { type: 'FeatureCollection',
      features: geo.features.filter((f) => PARTIAL[f.properties.NAME]) };
    L.geoJSON(partial, {
      pane: 'nocov', interactive: false,
      style: { color: '#9aa7b5', weight: 1.5, dashArray: '2 6',
        fill: true, fillOpacity: 0.02 },
    }).addTo(map);
    nocovFeatures = geo.features.filter(
      (f) => !COVERED.has(f.properties.NAME));
  } catch (e) { /* cosmetic layer; ignore */ }
});
// Ray-cast point-in-polygon over the decimated state outlines. Outer
// rings only; the coverage note does not need hole accuracy.
function nocovStateAt(latlng) {
  const x = latlng.lng, y = latlng.lat;
  for (const f of nocovFeatures) {
    const geom = f.geometry;
    const polys = geom.type === 'Polygon'
      ? [geom.coordinates] : geom.coordinates;
    for (const poly of polys) {
      const ring = poly[0];
      let inside = false;
      for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const xi = ring[i][0], yi = ring[i][1];
        const xj = ring[j][0], yj = ring[j][1];
        if ((yi > y) !== (yj > y)
            && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
      }
      if (inside) return f.properties.NAME;
    }
  }
  return null;
}
// A click that opened a dot popup, armed a route pick, or dismissed an
// open popup should never surface the coverage note; only a click that
// landed on nothing does.
let nocovHadPopup = false;
map.on('preclick', () => {
  nocovHadPopup = !!(map._popup && map._popup.isOpen());
});
map.on('click', (e) => {
  if (pickMode || nocovHadPopup || !nocovFeatures.length) return;
  const at = e.latlng;
  setTimeout(() => {
    if (map._popup && map._popup.isOpen()) return;
    const name = nocovStateAt(at);
    if (!name) return;
    const html = PARTIAL[name]
      ? '<div class="pop"><div class="t">' + esc(name) +
        '</div><div class="d">' + esc(name) +
        ' has partial coverage today: ' + esc(PARTIAL[name]) +
        '</div></div>'
      : '<div class="pop"><div class="t">' + esc(name) +
        '</div><div class="d">' + esc(name) + ' road data is not ' +
        'available yet. We add each state when its data feed comes ' +
        'online. Wildfires, weather alerts, and the live traffic ' +
        'overlay already cover the whole country: dots you see here ' +
        'are live and clickable.</div></div>';
    L.popup({ maxWidth: 270 }).setLatLng(at).setContent(html).openOn(map);
  }, 150);
});
document.getElementById('camvideo').addEventListener('change', rebuildCameras);

// ── Rail and panel ───────────────────────────────────────────────
// One tool open at a time; clicking the open tool collapses the panel
// so the rail alone remains. The choice and both widths persist per
// visitor (localStorage, best effort). The map re-measures after any
// layout change. Phones keep the stacked layout; the rail is a row.
const shellEl = document.getElementById('shell');
const railEl = document.getElementById('rail');
const TOOL_KEY = 'cs-tool';
const store = {
  get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (_) { /* private mode */ } },
};
function setTool(name, opts) {
  const toggle = !(opts && opts.toggle === false);
  const current = railEl.querySelector('.tool.on');
  const collapsing = toggle && current && current.dataset.tool === name
    && !shellEl.classList.contains('nopanel');
  railEl.querySelectorAll('.tool[data-tool]').forEach((b) => {
    const on = !collapsing && b.dataset.tool === name;
    b.classList.toggle('on', on);
    if (b.tagName === 'BUTTON') b.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
  document.querySelectorAll('aside section[data-tool]').forEach((s) => {
    s.classList.toggle('on', !collapsing && s.dataset.tool === name);
  });
  // The panel's search header shows on the tools that look at the map
  // (Places, Live); folded, the panel is the search alone.
  document.getElementById('panel').dataset.tool = collapsing ? '' : name;
  shellEl.classList.toggle('nopanel', !!collapsing);
  store.set(TOOL_KEY, collapsing ? '' : name);
  showWatch(name === 'watch' && !collapsing);
  // Settings shows the account: the watch module owns sign-in state.
  if (name === 'settings' && !collapsing) loadWatch();
  // Tools defined further down (Your places) listen for this.
  document.dispatchEvent(new CustomEvent('cs-tool', { detail: collapsing ? '' : name }));
  if (opts && opts.reveal && isPhone() && sheetState === 'peek') setSheet('half');
  setTimeout(() => map.invalidateSize(), 60);
}

// ── Watch tool: the /watch flow on this map, loaded on first use ──
// Firebase and the watch code only download when someone opens the
// tool. Its layers sit on the map while the tool is open.
let watchLoad = null;
function loadWatch() {
  const pane = document.getElementById('pane-watch');
  if (!watchLoad) {
    watchLoad = import(pane.dataset.src)
      .then((mod) => mod.initWatch({ map, visible: false,
        active: () => pane.classList.contains('on') }))
      .catch((err) => { console.error('watch tool failed to load', err); return null; });
  }
  return watchLoad;
}
function showWatch(on) {
  const pane = document.getElementById('pane-watch');
  if (!on && !watchLoad) return;
  loadWatch().then((w) => { if (w) w.setVisible(on && pane.classList.contains('on')); });
}
document.getElementById('settingssignin').addEventListener('click', () => {
  setTool('watch', { toggle: false, reveal: true });
});

// ── Settings: distance units ─────────────────────────────────────
{
  const pick = document.getElementById('unitpick');
  const note = document.getElementById('unitnote');
  const sync = () => {
    pick.querySelectorAll('input').forEach((i) => { i.checked = i.value === csUnits.get(); });
    note.textContent = csUnits.chosen()
      ? 'Saved on this device, and on your account when you are signed in.'
      : 'Following your device\'s locale (' +
        (csUnits.localeDefault() === 'mi' ? 'miles' : 'kilometers') + ') until you pick one.';
  };
  pick.addEventListener('change', (e) => { if (e.target.value) csUnits.set(e.target.value); });
  document.addEventListener('cs-units', () => {
    sync();
    if (lastEnds) replanVias();  // distances in the directions come from the router
  });
  sync();
}

// ── Phone: the panel is a bottom sheet, the rail its tab bar ─────
// Three resting heights. The handle drags (release snaps to the
// nearest stop) or taps to the next stop; arrow keys step. The tab bar
// never collapses the panel: the same tab again folds it to a peek.
const SHEET_KEY = 'cs-sheet';
const SHEET_STOPS = ['peek', 'half', 'full'];
const SHEET_PEEK = 84;
const phoneMq = window.matchMedia('(max-width: 960px)');
const isPhone = () => phoneMq.matches;
const panelEl = document.getElementById('panel');
const grabEl = document.getElementById('sheetgrab');
let sheetState = SHEET_STOPS.includes(store.get(SHEET_KEY)) ? store.get(SHEET_KEY) : 'half';
function setSheet(state) {
  if (!SHEET_STOPS.includes(state)) return;
  sheetState = state;
  panelEl.style.height = '';
  SHEET_STOPS.forEach((s) => shellEl.classList.toggle('sheet-' + s, s === state));
  store.set(SHEET_KEY, state);
}
setSheet(sheetState);
if (grabEl) {
  const stopHeights = () => {
    const h = shellEl.clientHeight;
    const tab = railEl.offsetHeight;
    return { peek: SHEET_PEEK, half: Math.round(h * 0.44), full: h - tab - 12 };
  };
  let drag = null;
  grabEl.addEventListener('pointerdown', (e) => {
    drag = { y: e.clientY, h: panelEl.getBoundingClientRect().height, moved: false };
    grabEl.setPointerCapture(e.pointerId);
    panelEl.classList.add('dragging');
  });
  grabEl.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const dy = drag.y - e.clientY;
    if (Math.abs(dy) > 4) drag.moved = true;
    const st = stopHeights();
    panelEl.style.height = Math.max(st.peek, Math.min(st.full, drag.h + dy)) + 'px';
  });
  const release = () => {
    if (!drag) return;
    panelEl.classList.remove('dragging');
    if (!drag.moved) {
      setSheet(SHEET_STOPS[(SHEET_STOPS.indexOf(sheetState) + 1) % SHEET_STOPS.length]);
    } else {
      const st = stopHeights();
      const h = panelEl.getBoundingClientRect().height;
      setSheet(SHEET_STOPS.reduce((a, s) =>
        (Math.abs(st[s] - h) < Math.abs(st[a] - h) ? s : a), 'peek'));
    }
    drag = null;
  };
  grabEl.addEventListener('pointerup', release);
  grabEl.addEventListener('pointercancel', release);
  grabEl.addEventListener('keydown', (e) => {
    const i = SHEET_STOPS.indexOf(sheetState);
    if (e.key === 'ArrowUp' && i < SHEET_STOPS.length - 1) { setSheet(SHEET_STOPS[i + 1]); e.preventDefault(); }
    if (e.key === 'ArrowDown' && i > 0) { setSheet(SHEET_STOPS[i - 1]); e.preventDefault(); }
  });
}

railEl.addEventListener('click', (e) => {
  const btn = e.target.closest('.tool');
  if (!btn || btn.tagName !== 'BUTTON' || !btn.dataset.tool) return;
  if (isPhone()) {
    const same = btn.classList.contains('on');
    setTool(btn.dataset.tool, { toggle: false });
    if (same && sheetState !== 'peek') setSheet('peek');
    else if (sheetState === 'peek') setSheet('half');
  } else {
    setTool(btn.dataset.tool);
  }
  if (btn.dataset.tool === 'alerts' && typeof scheduleAlerts === 'function') scheduleAlerts();
});
{
  const saved = store.get(TOOL_KEY);
  // A panel collapsed on a desktop has no meaning on a phone: the
  // sheet always shows one tool.
  // Your places is the front door: Home, Work, saved spots and what is
  // live around you. A tool that no longer exists falls back to it.
  const known = saved && railEl.querySelector('.tool[data-tool="' + saved + '"]');
  if (saved === '' && !isPhone()) setTool('places', { toggle: false }), setTool('places');
  else setTool(known ? saved : 'places', { toggle: false });
}
// Deep link: /map?settings=keys opens Settings at the API keys card (the
// docs' "Get a free key" button). Signed out, the card is hidden and the
// account note with its sign-in button is shown instead, so scroll to
// whichever of the two is visible once the account module has loaded.
// No parameter, no change.
if (new URLSearchParams(location.search).get('settings') === 'keys') {
  setTool('settings', { toggle: false, reveal: true });
  loadWatch().then(() => setTimeout(() => {
    const card = document.getElementById('keycard');
    const target = card && !card.hidden ? card : document.getElementById('acctnote');
    if (target) target.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }, 400));
}
// Drag handles. Bounds from the spec: the floating panel 300-520px and
// never more than 40% of the viewport; the details pane 300-480px. The
// rail is a fixed 76px (board #4), wider only when expanded.
const BOUNDS = {
  'cs-panel-w': { min: 300, max: () => Math.min(520, Math.round(window.innerWidth * 0.4)),
                  prop: '--panel-w' },
  'cs-insp-w': { min: 300, max: 480, prop: '--insp-user' },
};
function clampWidth(key, px) {
  const b = BOUNDS[key];
  const max = typeof b.max === 'function' ? b.max() : b.max;
  return Math.max(b.min, Math.min(max, Math.round(px)));
}
function applyWidth(key, px) {
  const w = clampWidth(key, px);
  shellEl.style.setProperty(BOUNDS[key].prop, w + 'px');
  store.set(key, String(w));
  return w;
}
for (const key of Object.keys(BOUNDS)) {
  const saved = Number(store.get(key));
  if (saved) applyWidth(key, saved);
}
function wireResizer(id, key, edge, dir) {
  const el = document.getElementById(id);
  if (!el) return;
  dir = dir || 1;  // 1: handle on the right edge; -1: on the left edge
  el.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    el.setPointerCapture(e.pointerId);
    el.classList.add('dragging');
    const move = (ev) => {
      applyWidth(key, dir * (ev.clientX - edge()));
    };
    const up = () => {
      el.classList.remove('dragging');
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerup', up);
      el.removeEventListener('pointercancel', up);
      setTimeout(() => map.invalidateSize(), 60);
    };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerup', up);
    el.addEventListener('pointercancel', up);
  });
  el.addEventListener('keydown', (e) => {
    const step = e.key === 'ArrowRight' ? 16 : e.key === 'ArrowLeft' ? -16 : 0;
    if (!step) return;
    e.preventDefault();
    const cur = parseInt(getComputedStyle(shellEl).getPropertyValue(BOUNDS[key].prop), 10)
      || BOUNDS[key].min;
    applyWidth(key, cur + dir * step);
    setTimeout(() => map.invalidateSize(), 60);
  });
}
wireResizer('panelresize', 'cs-panel-w',
  () => document.getElementById('panel').getBoundingClientRect().left);
wireResizer('inspresize', 'cs-insp-w',
  () => document.getElementById('inspector').getBoundingClientRect().right, -1);
window.addEventListener('resize', () => {
  const saved = Number(store.get('cs-panel-w'));
  if (saved) applyWidth('cs-panel-w', saved);
});
map.on('popupopen', async (e) => {
  const mk = (e.popup && e.popup.__m) ? e.popup
    : (e.popup && e.popup._source);
  const m = mk && mk.__m;
  if (!m || !(mk.__g || '').startsWith('clo_') || !Array.isArray(m.end)) return;
  // Re-sample after two minutes: the number is a live measurement,
  // not a cached guess.
  if (mk.__measuredHtml !== undefined
      && Date.now() - (mk.__measuredAt || 0) < 120000) {
    if (mk.__measuredHtml) appendMeasured(e.popup, mk.__measuredHtml);
    return;
  }
  mk.__measuredHtml = null;
  mk.__measuredAt = Date.now();
  const pts = (Array.isArray(m.path) && m.path.length > 1)
    ? m.path : [[m.lat, m.lon], m.end];
  let meters = 0;
  for (let i = 1; i < pts.length; i++) {
    meters += map.distance(pts[i - 1], pts[i]);
  }
  const mid = pts[Math.floor(pts.length / 2)];
  try {
    const res = await fetch('/api/flow?pts=' +
      mid[0].toFixed(4) + ',' + mid[1].toFixed(4));
    if (!res.ok) return;
    const f = ((await res.json()).flow || [])[0];
    if (!f || !f.current || !f.freeflow) return;
    const miles = meters / 1609.344;
    const delay = Math.max(0,
      miles * 60 * (1 / f.current - 1 / f.freeflow));
    let text;
    if (delay >= 1) {
      text = 'Measured now: ~' + Math.round(delay) + ' min over free flow '
        + 'across this ' + miles.toFixed(1) + ' mi stretch ('
        + Math.round(f.current) + ' vs ' + Math.round(f.freeflow)
        + ' mph, live TomTom sample)';
    } else if (f.ratio != null && f.ratio < 0.85) {
      text = 'Measured now: traffic here runs ' + Math.round(f.current)
        + ' vs ' + Math.round(f.freeflow) + ' mph free flow, but the '
        + 'stretch is short - under a minute of added time '
        + '(live TomTom sample)';
    } else {
      text = 'Measured now: traffic is moving at free-flow speed through '
        + 'this ' + miles.toFixed(1) + ' mi stretch ('
        + Math.round(f.current) + ' mph, live TomTom sample)';
    }
    mk.__measuredHtml = '<div class="hist" style="margin-top:5px">'
      + text + '</div>';
    if (e.popup.isOpen()) appendMeasured(e.popup, mk.__measuredHtml);
  } catch (err) { /* no sample, no line */ }
});

// Toll corridor popups: hovering (or tapping, on touch) a rate row
// lights up its entry point, destination, and the tolled stretch
// between them, so a price maps to a piece of road at a glance.
let tollHiLayers = [];
function tollHiClear() {
  tollHiLayers.forEach((l) => map.removeLayer(l));
  tollHiLayers = [];
}
function tollHighlight(m, gi, di) {
  tollHiClear();
  // Same filter as the popup renderer: row indices must line up.
  const entries = (m.entries || []).filter((e) => (e.rows || []).length);
  const g = entries[gi];
  if (!g) return;
  const mark = (pt) => tollHiLayers.push(L.circleMarker(pt, {
    renderer: canvasR, radius: 10, color: '#1d4ed8', weight: 3,
    fillColor: '#93c5fd', fillOpacity: 0.85 }).addTo(map));
  (g.pts || []).forEach(mark);
  if (di == null) return;
  const destLabel = ((g.rows || [])[di] || [])[0];
  // Destination coords may live on a rowless entry (an exit that
  // prices nothing itself): search the unfiltered list.
  const destEntry = destLabel
    && (m.entries || []).find((x) => x.label === destLabel);
  if (!destEntry || !destEntry.pts || !destEntry.pts.length) return;
  mark(destEntry.pts[0]);
  const segs = (Array.isArray(m.segs) && m.segs.length)
    ? m.segs : geoByKey.get('t' + geoKey(m));
  if (!Array.isArray(segs) || !segs.length) return;
  const flat = segs.flat();
  const near = (pt) => {
    let best = 0, bd = Infinity;
    for (let i = 0; i < flat.length; i++) {
      const d = Math.hypot(flat[i][0] - pt[0], flat[i][1] - pt[1]);
      if (d < bd) { bd = d; best = i; }
    }
    return best;
  };
  const a = near((g.pts || [])[0]), b = near(destEntry.pts[0]);
  const piece = flat.slice(Math.min(a, b), Math.max(a, b) + 1);
  if (piece.length > 1) {
    // Sanity gate: a slice much longer than the crow-flies distance
    // means the flattened geometry is not monotone here (data quirk);
    // endpoint markers alone beat drawing a misleading loop.
    let plen = 0;
    for (let i = 1; i < piece.length; i++) {
      plen += map.distance(piece[i - 1], piece[i]);
    }
    const direct = map.distance(g.pts[0], destEntry.pts[0]);
    if (plen <= direct * 3 + 500) {
      tollHiLayers.push(L.polyline(piece, {
        renderer: canvasR, color: '#1d4ed8', weight: 8, opacity: 0.8,
      }).addTo(map));
    }
  }
}
// Toll details render in the left-hand panel (openTollPanel), which
// wires its own hover highlighting; popups only need the clear-on-
// close hook.
map.on('popupclose', tollHiClear);

function appendMeasured(popup, html) {
  const el = popup.getElement();
  const box = el && el.querySelector('.pop');
  if (box && !box.querySelector('.measured')) {
    const div = document.createElement('div');
    div.className = 'measured';
    div.innerHTML = html;
    // No popup.update() here: it re-renders from the original content
    // string and would wipe this node.
    box.append(div);
  }
}


// ── Data-source status panel: click "live from ..." in the topbar ──
let srcPanel = null;
async function renderSourcePanel() {
  if (!srcPanel) return;
  srcPanel.innerHTML = '<h4>Data sources</h4><div class="sub">Loading&hellip;</div>';
  try {
    const res = await fetch('/api/sources');
    const d = await res.json();
    const at = new Date(d.checked_at);
    srcPanel.innerHTML = '<h4>Data sources</h4>' +
      '<div class="sub">Checked ' + at.toLocaleString([], {
        hour: 'numeric', minute: '2-digit', weekday: 'short' }) + '</div>';
    // Group per state (California first, then expansion states, then
    // nationwide pieces) so each region's health reads at a glance.
    const order = ['California'];
    for (const s of d.sources) {
      const st = s.state || 'Other';
      if (!order.includes(st) && st !== 'Nationwide') order.push(st);
    }
    order.push('Nationwide');
    const grouped = [];
    for (const st of order) {
      grouped.push({ header: st });
      for (const s of d.sources) if ((s.state || 'Other') === st) grouped.push(s);
    }
    for (const g of grouped) {
      if (g.header) {
        const h = document.createElement('h5');
        h.textContent = g.header;
        h.style.cssText = 'font:700 .64rem Inter;text-transform:uppercase;' +
          'letter-spacing:.6px;color:var(--dim);margin:9px 0 2px';
        srcPanel.append(h);
        continue;
      }
      const s = g;
      const row = document.createElement('div');
      row.className = 'src';
      const dot = document.createElement('i');
      let state, color;
      if (s.on_demand) { state = 'queried per route'; color = '#2f81f7'; }
      else if ('enabled' in s) {
        state = s.enabled ? 'active' : 'no key set';
        color = s.enabled ? '#2f9e6e' : '#9aa7b5';
      } else if (!s.ok) { state = 'unavailable'; color = '#d64545'; }
      else if (s.stale) { state = 'serving cached data'; color = '#e8a13c'; }
      else { state = 'online'; color = '#2f9e6e'; }
      dot.style.background = color;
      const name = document.createElement('span');
      name.textContent = s.name + ', ' + s.agency;
      const meta = document.createElement('small');
      const ago = s.as_of ? agoTxt(s.as_of) : null;
      meta.textContent = state + (ago ? ', data ' + ago : '');
      if (s.error) meta.title = s.error;
      row.append(dot, name, meta);
      srcPanel.append(row);
    }
  } catch (_) {
    srcPanel.innerHTML = '<h4>Data sources</h4><div class="sub">Status unavailable right now.</div>';
  }
}
// The topbar's "live from ..." and the map's live pill open the same
// list; from the pill it rises above the pill.
function toggleSrcPanel(from) {
  const pill = document.getElementById('livepill');
  if (srcPanel) { srcPanel.remove(); srcPanel = null; pill.setAttribute('aria-expanded', 'false'); return; }
  srcPanel = document.createElement('div');
  srcPanel.className = 'srcpanel';
  srcPanel.id = 'srcpanel';
  if (from === pill) {
    const r = pill.getBoundingClientRect();
    srcPanel.classList.add('frompill');
    srcPanel.style.left = Math.max(12, Math.min(r.left, innerWidth - 312)) + 'px';
    srcPanel.style.bottom = (innerHeight - r.top + 8) + 'px';
    pill.setAttribute('aria-expanded', 'true');
  }
  document.body.append(srcPanel);
  renderSourcePanel();
}
document.getElementById('sysok').addEventListener('click', (e) => toggleSrcPanel(e.currentTarget));
document.getElementById('livepill').addEventListener('click', (e) => toggleSrcPanel(e.currentTarget));
document.addEventListener('click', (e) => {
  if (srcPanel && !srcPanel.contains(e.target) &&
      !document.getElementById('sysok').contains(e.target) &&
      !document.getElementById('livepill').contains(e.target)) {
    srcPanel.remove(); srcPanel = null;
    document.getElementById('livepill').setAttribute('aria-expanded', 'false');
  }
});

// "Show dispatch log" in incident popups: lazy-fetch the full CHP
// timeline only when someone asks for it, newest entries first.
function wireDispatchLog(el, popup) {
  const btn = el && el.querySelector('.detbtn[data-inc]');
  if (!btn || btn.dataset.wired) return;
  btn.dataset.wired = '1';
  btn.addEventListener('click', async () => {
    const box = el.querySelector('.dets');
    btn.textContent = 'Loading…'; btn.disabled = true;
    try {
      const res = await fetch('/api/incident/' + encodeURIComponent(btn.dataset.inc));
      if (!res.ok) throw new Error('unavailable');
      const d = await res.json();
      let h = '';
      // CHP numbers each comment ("[18] ..."), so sort by that index,
      // newest first; entries without one keep their feed position.
      const seq = (en) => {
        const m2 = /^\[(\d+)\]/.exec(en[1] || '');
        return m2 ? Number(m2[1]) : -1;
      };
      // CHP stamps look like "Jul 29 2026 12:51AM" (no space before
      // AM), which Date.parse rejects: pull the clock straight out.
      const clock = (s) => {
        const m2 = /(\d{1,2}:\d{2})\s*(AM|PM)/i.exec(s || '');
        return m2 ? m2[1] + ' ' + m2[2].toUpperCase() : esc(s || '');
      };
      const row = (en) => {
        const xl = explainLine(en[1] || '');
        return '<div class="lgrow"><time>' + clock(en[0]) + '</time><div>' +
          '<div class="raw">' + esc(en[1] || '') + '</div>' +
          (xl ? '<div class="xpl">' + esc(xl) + '</div>' : '') +
          '</div></div>';
      };
      if (d.details && d.details.length) {
        h += '<div class="lg"><h5>Dispatch log (newest first)</h5>' +
          '<div class="lgkey">Blue text is a rough translation of the CHP shorthand.</div>' +
          d.details.map((en, i) => [en, seq(en) >= 0 ? seq(en) : i])
            .sort((x, y) => y[1] - x[1]).map(([en]) => row(en)).join('') +
          '</div>';
      }
      // The units feed is a flat pile of status flips with no unit
      // names: each unit's events arrive newest-first and end at its
      // "Unit Assigned" row, so split there and tell one unit's story
      // per line.
      const groups = [];
      let cur = [];
      for (const en of d.units || []) {
        cur.push(en);
        if (/assigned/i.test(en[1] || '')) { groups.push(cur); cur = []; }
      }
      if (cur.length) groups.push(cur);
      if (groups.length) {
        const STATUS = { assigned: 'assigned', enroute: 'en route',
          'at scene': 'on scene', cleared: 'cleared to leave' };
        const unitRows = groups.map((grp, i) => {
          const events = grp.slice().reverse().map((en) => {
            const key = (en[1] || '').replace(/^Unit\s*/i, '').toLowerCase();
            // esc(): key falls back to raw CHP unit-status feed text.
            return esc(STATUS[key] || key) + ' ' + clock(en[0]);
          });
          const done = /cleared/i.test(grp[0] && grp[0][1] || '');
          return '<div class="urow"><b>Unit ' + (i + 1) + '</b><span>' +
            events.join(', ') + (done ? '' : '. Still working the scene') +
            '</span></div>';
        }).join('');
        h += '<div class="lg"><h5>CHP units on this call (' + groups.length + ')</h5>' +
          '<div class="lgkey">One line per unit. "Cleared to leave" means the unit ' +
          'finished its part and left the scene. CHP does not name units in the ' +
          'public feed.</div>' + unitRows + '</div>';
      }
      // No popup.update() here: it re-renders from the original content
      // string and would wipe this injected log (same rule as
      // appendMeasured above). The .dets box scrolls within max-height.
      box.innerHTML = h || '<div class="drow">No shared entries yet.</div>';
      // A timeline reads badly at 320px: widen the popup while the log
      // is open, then recompute layout and position so the tip stays
      // anchored on the dot (skipping _updateContent keeps the
      // injected log; popup.update() would wipe it).
      const cw = el.querySelector('.leaflet-popup-content');
      if (cw && h && popup) {
        cw.style.width = Math.min(500, window.innerWidth - 70) + 'px';
        popup._updateLayout();
        popup._updatePosition();
      }
      btn.remove();
    } catch (_) {
      btn.textContent = 'Log unavailable right now'; btn.disabled = true;
    }
  });
}
map.on('popupopen', (e) => wireDispatchLog(e.popup.getElement(), e.popup));

// ── Inspector: a wider pane for what a popup cannot hold ─────────
// Opened on demand from a popup's button or an Alerts row; the same
// builder renders it, with room for the full still, the whole dispatch
// log, and the sign board.
const inspectorEl = document.getElementById('inspector');
const inspBody = document.getElementById('inspbody');
const inspTitle = document.getElementById('insptitle');
const inspResize = document.getElementById('inspresize');
// A share link only makes sense for kinds a focus link can find again.
function focusKind(g) {
  return Object.keys(FOCUS_GROUPS).find((k) => FOCUS_GROUPS[k].includes(g)) || null;
}
// The inspector is a page of its own, not a popup in a column: a header
// with the kind's picture in its color, the title large, the facts as a
// table, and the actions pinned to the bottom where a thumb or a mouse
// finds them without scrolling.
const inspIcon = document.getElementById('inspicon');
const inspWhen = document.getElementById('inspwhen');
const inspFoot = document.getElementById('inspfoot');
const INSP_GLYPH = {
  inc_collision: 'crash', inc_fire: 'fire', inc_hazard: 'hazard', inc_other: 'incident',
  clo_full: 'closed', clo_lane: 'closed', clo_oneway: 'closed', clo_ramp: 'closed',
  chain: 'snow', rwis: 'thermo', fire_pt: 'fire', fire_poly: 'fire', toll: 'toll',
  camera: 'video', sign: 'sign',
};
function inspectorActions(m, g) {
  const row = document.createDocumentFragment();
  function button(id, label, primary, onClick) {
    const b = document.createElement('button');
    b.type = 'button'; b.id = id; b.textContent = label;
    b.className = primary ? 'inspact primary' : 'inspact';
    b.addEventListener('click', () => onClick(b));
    row.appendChild(b);
    return b;
  }
  if (Number.isFinite(m.lat) && Number.isFinite(m.lon)) {
    button('inspcenter', 'Show on map', true, () => {
      map.setView([m.lat, m.lon], Math.max(map.getZoom(), 13));
    });
  }
  const kind = focusKind(g);
  if (kind && Number.isFinite(m.lat) && Number.isFinite(m.lon)) {
    button('inspshare', 'Copy link', false, async (share) => {
      const url = location.origin + '/map?focus=' + m.lat.toFixed(5) + ',' +
        m.lon.toFixed(5) + '&k=' + kind;
      try {
        await navigator.clipboard.writeText(url);
        share.textContent = 'Link copied';
        setTimeout(() => { share.textContent = 'Copy link'; }, 1800);
      } catch (_) { showLinkInline(share, url); }
    });
  }
  button('inspwatch', 'Watch this stretch', false, () => {
    closeInspector();
    setTool('watch', { toggle: false, reveal: true });
    if (watchLoad) watchLoad.then((w) => { if (w) w.watchHere(m.lat, m.lon); });
  });
  return row;
}
// Basic or Advanced, remembered per visitor. Basic is the popup's own
// account of the item; Advanced is the record itself: timing, source,
// IDs, every field, and the JSON, each said once.
const INSP_MODE_KEY = 'cs-insp-mode';
const inspScroll = document.getElementById('inspscroll');
const inspAdv = document.getElementById('inspadv');
const inspAi = document.getElementById('inspai');
const inspAiText = document.getElementById('inspaitext');
const inspTabs = Array.from(document.querySelectorAll('#inspmode [role="tab"]'));
let inspMode = store.get(INSP_MODE_KEY) === 'advanced' ? 'advanced' : 'basic';
let inspItem = null;        // { m, g } on show
let inspOpener = null;      // focus returns here when the pane closes
let inspGen = 0;
function setInspMode(mode, focusTab) {
  inspMode = mode === 'advanced' ? 'advanced' : 'basic';
  store.set(INSP_MODE_KEY, inspMode);
  inspTabs.forEach((t) => {
    const on = t.dataset.mode === inspMode;
    t.setAttribute('aria-selected', on ? 'true' : 'false');
    t.tabIndex = on ? 0 : -1;
    if (on && focusTab) t.focus();
  });
  inspBody.hidden = inspMode !== 'basic';
  inspAdv.hidden = inspMode !== 'advanced';
  if (inspMode === 'advanced' && inspItem && !inspAdv.dataset.built) {
    inspAdv.replaceChildren(advancedView(inspItem.m, inspItem.g));
    inspAdv.dataset.built = '1';
  }
}
inspTabs.forEach((t, i) => {
  t.addEventListener('click', () => setInspMode(t.dataset.mode));
  t.addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    e.preventDefault();
    setInspMode(inspTabs[(i + 1) % inspTabs.length].dataset.mode, true);
  });
});
function openInspector(m, g) {
  const plugin = g === 'plugin';
  const acc = plugin ? csPlugin.color(csPlugin.sourceId(m)) : (GROUP_DOT[g] || '#64748b');
  inspectorEl.style.setProperty('--acc', acc);
  inspIcon.innerHTML = csPlugin.svg(plugin ? csPlugin.category(m.flare_kind) : (INSP_GLYPH[g] || 'other'));
  inspIcon.classList.toggle('square', plugin);
  const label = plugin ? (m.source || 'Plugin') : (POP_LABEL[g] || 'Details').toLowerCase();
  const kind = label.charAt(0).toUpperCase() + label.slice(1);
  inspBody.innerHTML = popupFor(m, g);
  // Board #9: the header carries the item's own title, and under it the
  // kind, the place line and "how long ago"; the body then starts with
  // what the header does not say, so nothing is shown twice.
  const ago = inspBody.querySelector('.ago');
  const h4 = inspBody.querySelector('h4');
  const sub = inspBody.querySelector('.p2 > .sub, .pop > .sub');
  inspTitle.textContent = h4 ? h4.textContent : kind;
  inspWhen.textContent = [h4 ? kind : null, sub ? sub.textContent : null, ago ? ago.textContent : null]
    .filter(Boolean).join(' · ');
  for (const el of [inspBody.querySelector('.p2 > .hd'), h4, sub]) if (el) el.classList.add('inhead');
  inspScroll.scrollTop = 0;
  wireDispatchLog(inspBody, null);
  if (g === 'toll') {
    // Hover a rate row: light up that stretch of the corridor.
    inspBody.querySelectorAll('[data-tg]').forEach((row) => {
      const gi = +row.dataset.tg;
      const di = row.dataset.td !== undefined ? +row.dataset.td : null;
      row.addEventListener('mouseenter', () => tollHighlight(m, gi, di));
      row.addEventListener('mouseleave', tollHiClear);
      row.addEventListener('click', () => tollHighlight(m, gi, di));
    });
  }
  inspFoot.replaceChildren(inspectorActions(m, g));
  inspItem = { m, g };
  delete inspAdv.dataset.built;
  inspAdv.replaceChildren();
  setInspMode(inspMode);
  loadOverview(m, g, ++inspGen);
  const wasHidden = inspectorEl.hidden;
  if (wasHidden) {
    const active = document.activeElement;
    inspOpener = active && active !== document.body && !inspectorEl.contains(active) ? active : null;
  }
  inspectorEl.hidden = false;
  if (inspResize) inspResize.hidden = false;
  shellEl.classList.add('insp');
  if (isPhone()) setSheet('peek');
  // Focus moves into the pane so a keyboard user lands on what opened.
  document.getElementById('inspclose').focus({ preventScroll: true });
  setTimeout(() => map.invalidateSize(), 60);
}
function closeInspector() {
  if (inspectorEl.hidden) return;
  inspectorEl.hidden = true;
  if (inspResize) inspResize.hidden = true;
  shellEl.classList.remove('insp');
  inspBody.innerHTML = '';
  inspAdv.replaceChildren();
  inspItem = null;
  inspGen += 1;
  inspAi.hidden = true;
  tollHiClear();
  if (inspOpener && document.contains(inspOpener)) inspOpener.focus({ preventScroll: true });
  inspOpener = null;
  setTimeout(() => map.invalidateSize(), 60);
}
document.getElementById('inspclose').addEventListener('click', closeInspector);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeInspector(); });

// ── One-line AI overview at the top of the pane ──────────────────
// Asked for lazily, once per item (the server caches too), never on the
// critical path: a calm placeholder while it loads, and on any error or
// limit the line simply is not there.
const overviewCache = new Map();
const OVERVIEW_SKIP = new Set(['camera']);  // a camera has nothing to summarise
function overviewRecord(m) {
  const out = {};
  for (const [k, v] of Object.entries(m)) {
    if (k.startsWith('_') || ['path', 'poly', 'segs', 'entries', 'image', 'stream'].includes(k)) continue;
    if (v == null || typeof v !== 'object') out[k] = v;
    else if (Array.isArray(v) && v.length <= 12 && v.every((x) => x == null || typeof x !== 'object')) out[k] = v;
  }
  return out;
}
async function loadOverview(m, g, gen) {
  inspAi.hidden = true;
  inspAi.classList.remove('loading');
  if (OVERVIEW_SKIP.has(g)) return;
  const record = overviewRecord(m);
  const key = g + '|' + JSON.stringify(record);
  let hit = overviewCache.get(key);
  if (hit === null) return;  // failed before: do not ask again this visit
  if (!hit) {
    inspAiText.textContent = '';
    inspAi.classList.add('loading');
    inspAi.hidden = false;
    hit = fetch('/api/overview', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: POP_LABEL[g] || g, record, tz: VIEWER_TZ }),
    }).then((r) => (r.ok ? r.json() : null)).then((d) => (d && d.overview) || null)
      .catch(() => null);
    overviewCache.set(key, hit);
    if (overviewCache.size > 200) overviewCache.delete(overviewCache.keys().next().value);
  }
  const text = await hit;
  if (!text) overviewCache.set(key, null);
  if (gen !== inspGen) return;
  inspAi.classList.remove('loading');
  if (!text) { inspAi.hidden = true; return; }
  inspAiText.textContent = text;
  inspAi.hidden = false;
}

// ── Advanced: the record itself ──────────────────────────────────
const TIME_KEYS = /^(reported|since|until|updated|discovered|as_of|start|end|starts|ends|created|modified|observed|time|ts|last_updated|[a-z]+_at)$/;
const ID_KEYS = /^(id|uid|key|inc|incident_id|event_id|[a-z]+_id)$/;
const GEOM_KEYS = new Set(['path', 'poly', 'segs', 'entries', 'lane_layout']);
function asTime(v) {
  if (typeof v === 'number' && v > 1e8) return new Date(v < 1e12 ? v * 1000 : v);
  if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(v)) {
    const d = new Date(v);
    return Number.isFinite(d.getTime()) ? d : null;
  }
  return null;
}
function relTime(d) {
  const mins = Math.round((d.getTime() - Date.now()) / 60000);
  const a = Math.abs(mins);
  const txt = a < 1 ? 'now' : a < 60 ? a + ' min' : a < 48 * 60 ? Math.round(a / 60) + ' h'
    : Math.round(a / 1440) + ' days';
  return a < 1 ? 'now' : mins < 0 ? txt + ' ago' : 'in ' + txt;
}
function countPoints(v) {
  let n = 0;
  const walk = (x) => {
    if (!Array.isArray(x)) return;
    if (x.length === 2 && typeof x[0] === 'number' && typeof x[1] === 'number') { n += 1; return; }
    x.forEach(walk);
  };
  walk(v);
  return n;
}
function fieldText(k, v) {
  if (v == null || v === '') return '—';
  if (GEOM_KEYS.has(k) || (Array.isArray(v) && v.length > 12)) {
    const pts = countPoints(v);
    if (pts) return pts.toLocaleString() + ' points';
    if (Array.isArray(v)) return v.length.toLocaleString() + ' entries';
    return Object.keys(v).length + ' fields (in the JSON below)';
  }
  if (Array.isArray(v)) return v.map((x) => (typeof x === 'object' ? JSON.stringify(x) : String(x))).join(' / ');
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}
// Long coordinate arrays stay in the copy and the download, but the
// on-screen JSON shows how many points they hold instead of a wall.
function displayJson(m) {
  return JSON.stringify(m, (k, v) => {
    if (k && Array.isArray(v) && (GEOM_KEYS.has(k) || v.length > 24)) {
      const pts = countPoints(v);
      return '[' + (pts ? pts.toLocaleString() + ' points' : v.length + ' items') + ' in the copy]';
    }
    return v;
  }, 2);
}
function advancedView(m, g) {
  const frag = document.createDocumentFragment();
  const section = (title, note) => {
    const sec = document.createElement('section');
    sec.className = 'advsec';
    const h = document.createElement('h5');
    h.textContent = title;
    sec.append(h);
    if (note) {
      const p = document.createElement('p');
      p.className = 'advnote';
      p.textContent = note;
      sec.append(p);
    }
    frag.append(sec);
    return sec;
  };
  const table = (sec, rows, mono) => {
    const dl = document.createElement('dl');
    dl.className = 'advtbl' + (mono ? ' mono' : '');
    for (const [k, v, extra] of rows) {
      const dt = document.createElement('dt'); dt.textContent = k;
      const dd = document.createElement('dd'); dd.textContent = v;
      if (extra) { const sm = document.createElement('small'); sm.textContent = extra; dd.append(sm); }
      dl.append(dt, dd);
    }
    sec.append(dl);
  };
  // Timing: every time the record carries, in your zone and relative,
  // then how fresh the map's copy is.
  const timeRows = [];
  for (const [k, v] of Object.entries(m)) {
    if (!TIME_KEYS.test(k)) continue;
    const d = asTime(v);
    if (d) timeRows.push([k, d.toLocaleString([], { month: 'short', day: 'numeric',
      year: d.getFullYear() === new Date().getFullYear() ? undefined : 'numeric',
      hour: 'numeric', minute: '2-digit', timeZoneName: 'short' }), relTime(d)]);
  }
  if (snapPublished) {
    const d = new Date(snapPublished);
    timeRows.push(['data_as_of', d.toLocaleString([], { hour: 'numeric', minute: '2-digit',
      second: '2-digit', timeZoneName: 'short' }), relTime(d) + ', when this map copy was published']);
  }
  if (timeRows.length) table(section('Timing'), timeRows);
  // Source and identity.
  const src = m.src || m.source || SOURCE_DEFAULT[g] || null;
  const idRows = [];
  if (src) idRows.push(['source', String(src)]);
  idRows.push(['kind', String(m.kind || '—'), 'map group: ' + g]);
  for (const [k, v] of Object.entries(m)) {
    if (ID_KEYS.test(k) && v != null && typeof v !== 'object') idRows.push([k, String(v)]);
  }
  if (Number.isFinite(m.lat) && Number.isFinite(m.lon)) {
    idRows.push(['lat, lon', m.lat.toFixed(5) + ', ' + m.lon.toFixed(5)]);
  }
  table(section('Source and IDs'), idRows, true);
  // Every field, in the record's own order, once.
  const shown = new Set(['src', 'source', 'kind', 'lat', 'lon']);
  idRows.forEach(([k]) => shown.add(k));
  timeRows.forEach(([k]) => shown.add(k));
  const rest = Object.keys(m).filter((k) => !shown.has(k) && !k.startsWith('_'))
    .map((k) => [k, fieldText(k, m[k])]);
  if (rest.length) table(section('Every other field'), rest, true);
  // The record as JSON, copyable and downloadable in full.
  const js = section('Record JSON',
    'This is the record as CommuteScout publishes it, after normalising the agency feed. ' +
    'The agency\'s original payload is not kept in the browser.' +
    (g.startsWith('inc_') && m.log_n ? ' For CHP incidents the dispatch log, in Basic, is the closest raw source.' : ''));
  const bar = document.createElement('div');
  bar.className = 'advbar';
  const full = JSON.stringify(m, null, 2);
  const copy = document.createElement('button');
  copy.type = 'button'; copy.className = 'inspact'; copy.textContent = 'Copy JSON';
  copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(full);
      copy.textContent = 'Copied';
    } catch (_) { copy.textContent = 'Copy failed: select the text below'; }
    setTimeout(() => { copy.textContent = 'Copy JSON'; }, 1800);
  });
  const dl = document.createElement('button');
  dl.type = 'button'; dl.className = 'inspact'; dl.textContent = 'Download .json';
  dl.addEventListener('click', () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([full], { type: 'application/json' }));
    a.download = (m.kind || g) + '-' + (m.id || (Number.isFinite(m.lat) ? m.lat.toFixed(4) + '_' + m.lon.toFixed(4) : 'record')) + '.json';
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  bar.append(copy, dl);
  const pre = document.createElement('pre');
  pre.className = 'advjson';
  pre.tabIndex = 0;
  pre.setAttribute('aria-label', 'Record JSON');
  pre.textContent = displayJson(m);
  js.append(bar, pre);
  return frag;
}

// Every marker popup is a peek: what it is, where, and the one line that
// matters, with one "Details" button that opens the pane. Appended at
// open time so the popup builders stay untouched; the fuller sections
// are folded by CSS (.peek), never removed.
map.on('popupopen', (e) => {
  const src = (e.popup && e.popup.__m) ? e.popup : (e.popup && e.popup._source);
  const m = src && src.__m;
  const g = src && src.__g;
  const el = e.popup.getElement();
  const box = el && el.querySelector('.p2, .pop');
  if (!m || !g || !box || box.querySelector('.inspbtn')) return;
  el.querySelectorAll('.p2, .pop').forEach((b) => b.classList.add('peek'));
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'detbtn inspbtn';
  btn.innerHTML = 'Details <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>';
  btn.setAttribute('aria-label', 'Open the details pane');
  btn.addEventListener('click', () => { openInspector(m, g); map.closePopup(); });
  box.appendChild(btn);
  e.popup._updateLayout();
  e.popup._updatePosition();
  // Opened from the keyboard (a list, the strip, the palette): focus
  // follows into the popup instead of staying on a control behind it.
  const active = document.activeElement;
  if (active && active !== document.body && !map.getContainer().contains(active)) {
    btn.focus({ preventScroll: true });
  }
});

// On a phone a popup is the point: fold the sheet to a peek and nudge
// the map so the popup clears both the sheet and the top edge.
map.on('popupopen', (e) => {
  if (!isPhone()) return;
  setSheet('peek');
  setTimeout(() => {
    const el = e.popup.getElement();
    if (!el || !e.popup.isOpen()) return;
    const r = el.getBoundingClientRect();
    const box = map.getContainer().getBoundingClientRect();
    const limit = box.bottom - SHEET_PEEK - railEl.offsetHeight - 8;
    if (r.bottom > limit) map.panBy([0, r.bottom - limit]);
    else if (r.top < box.top + 8) map.panBy([0, r.top - box.top - 8]);
  }, 320);
});

// ── Alerts: what is in view, worst first ─────────────────────────
// Reads the same items[] the renderer culls from, so it costs nothing
// extra to fetch; only the groups switched on in Layers count.
const SEVERITY = { clo_full: 0, inc_collision: 1, inc_fire: 1, chain: 2,
  inc_hazard: 2, fire_pt: 2, plugin: 2, clo_lane: 3, clo_oneway: 4, clo_ramp: 5,
  inc_other: 5 };
const SOURCE_DEFAULT = { inc_collision: 'CHP', inc_fire: 'CHP', inc_hazard: 'CHP',
  inc_other: 'CHP', clo_full: 'Caltrans', clo_lane: 'Caltrans',
  clo_oneway: 'Caltrans', clo_ramp: 'Caltrans', chain: 'Caltrans',
  fire_pt: 'WFIGS', plugin: 'community' };
const ALERT_CAP = 60;
const alertList = document.getElementById('alertlist');
let alertsTimer = null;
function groupOn(g) {
  const box = document.querySelector('#filters input[data-group="' + g + '"]');
  return !box || box.checked;
}
// The marketplace's per-browser switches: cs.plugins.off hides a listed
// plugin; an unlisted plugin (shared by link) shows only once it is in
// cs.plugins.on. A /map?plugin=<id> link installs that plugin first.
function pluginSwitches() {
  let off = '', on = '';
  try { off = localStorage.getItem('cs.plugins.off') || ''; on = localStorage.getItem('cs.plugins.on') || ''; } catch (e) { /* private mode */ }
  return { off: off.split(',').filter(Boolean), on: on.split(',').filter(Boolean) };
}
function pluginHidden(m) {
  const sid = m.source_id || String(m.id || '').split(':')[0];
  const sw = pluginSwitches();
  if (sw.off.includes(sid)) return true;
  return !!m.unlisted && !sw.on.includes(sid);
}
(function installLinkedPlugin() {
  const sid = new URLSearchParams(location.search).get('plugin');
  if (!sid) return;
  const sw = pluginSwitches();
  try {
    localStorage.setItem('cs.plugins.off', sw.off.filter((x) => x !== sid).join(','));
    if (!sw.on.includes(sid)) localStorage.setItem('cs.plugins.on', sw.on.concat([sid]).join(','));
  } catch (e) { /* private mode */ }
})();
// One row reads like the popup head: what it is, then where.
function alertRow(m, g) {
  const src = m.src || SOURCE_DEFAULT[g] || '';
  if (g.startsWith('inc_')) {
    const parts = splitRoad(m.label || '');
    // CHP types carry a dispatch code; incidentTitle drops it (and humanize(m.type) the rest).
    return { title: incidentTitle(m.type) || 'Incident',
      sub: [m.location || parts.road || parts.rest || null,
        m.reported ? agoTxt(m.reported) : null, src].filter(Boolean).join(', ') };
  }
  if (g.startsWith('clo_')) {
    const kind = { clo_full: 'Road closed', clo_lane: 'Lanes closed',
      clo_oneway: 'One-way traffic', clo_ramp: 'Ramp closed' }[g] || 'Closure';
    return { title: shapeShout(m.detail || m.label) ||
        [m.route, m.county].filter(Boolean).join(', ') || kind,
      sub: [kind, m.county ? m.county + ' County' : null, src].filter(Boolean).join(', ') };
  }
  if (g === 'chain') {
    return { title: (m.status ? m.status.toUpperCase().replace(/^R(\d)$/, 'R-$1') + ' on ' : '') +
        (m.route || 'Mountain pass'),
      sub: ['Chain control', (m.label || '').slice(0, 80), src].filter(Boolean).join(', ') };
  }
  if (g === 'plugin') {
    return { title: esc(humanize((m.flare_kind || 'OTHER').toLowerCase().replace(/_/g, ' '))),
      sub: [m.label || m.road || null, m.reported ? agoTxt(m.reported) : null,
        m.source || 'community'].filter(Boolean).join(', ') };
  }
  if (g === 'fire_pt') {
    const size = m.acres ? Math.round(m.acres).toLocaleString() + ' acres' : null;
    const cont = (m.contained || m.contained === 0) ? m.contained + '% contained' : null;
    return { title: (m.name || 'Wildfire') + ' Fire',
      sub: ['Wildfire', size, cont, src].filter(Boolean).join(', ') };
  }
  if (g === 'rwis') {
    const air = m.air_c != null ? Math.round(m.air_c * 9 / 5 + 32) + '\u00b0F air' : null;
    return { title: 'Road weather, ' + (m.label || m.name || m.route || 'station'),
      sub: [air, src].filter(Boolean).join(', ') };
  }
  if (g === 'sign') {
    // What the sign says is the news; the road is the place line.
    const lines = (m.lines && m.lines.length) ? m.lines : (m.message ? m.message.split(' / ') : []);
    const said = lines.map((l) => String(l).trim()).filter(Boolean).join(' ');
    if (said) {
      return { title: 'Sign: ' + said,
        sub: [m.label || m.name || m.route || null, src].filter(Boolean).join(', ') };
    }
  }
  return { title: m.label || m.name || m.route || POP_LABEL[g] || g, sub: src };
}
function refreshAlerts() {
  if (!alertList || !document.getElementById('pane-alerts').classList.contains('on')) return;
  const b = map.getBounds();
  const c = map.getCenter();
  const rows = [];
  for (const g of Object.keys(SEVERITY)) {
    if (!items[g] || !groupOn(g)) continue;
    for (const it of items[g]) {
      const m = it.m;
      if (!b.contains([m.lat, m.lon])) continue;
      rows.push({ it, sev: SEVERITY[g], d: map.distance(c, [m.lat, m.lon]) });
    }
  }
  rows.sort((x, y) => x.sev - y.sev || x.d - y.d);
  const top = rows.slice(0, ALERT_CAP);
  if (!top.length) {
    alertList.innerHTML = '<p class="panenote">Nothing in view for the layers ' +
      'you have on. Zoom out or turn on more layers.</p>';
    return;
  }
  alertList.innerHTML = top.map((r, i) => {
    const m = r.it.m;
    const g = r.it.g;
    const row = alertRow(m, g);
    return '<button type="button" class="alertrow" data-i="' + i + '">' +
      kindIcon(g) + '<span><b>' +
      esc(String(row.title).slice(0, 110)) + '</b><small>' + esc(row.sub) +
      '</small></span></button>';
  }).join('') + (rows.length > ALERT_CAP
    ? '<p class="panenote">Showing the ' + ALERT_CAP + ' worst of ' + rows.length +
      ' in view.</p>' : '');
  alertList.querySelectorAll('.alertrow').forEach((btn) => {
    btn.addEventListener('click', () => {
      const r = top[+btn.dataset.i];
      if (!r) return;
      const m = r.it.m;
      const at = L.latLng(m.lat, m.lon);
      const z = Math.max(map.getZoom(), 11);
      const open = () => {
        const p = L.popup({ maxWidth: 320 }).setLatLng(at).setContent(popupFor(m, r.it.g));
        p.__m = m; p.__g = r.it.g;
        p.openOn(map);
      };
      // Open once the move has landed, so the popup's auto-pan sees the
      // final view rather than a frame of the animation.
      if (map.getCenter().distanceTo(at) < 1 && map.getZoom() === z) open();
      else { map.once('moveend', open); map.setView(at, z); }
    });
  });
}
function scheduleAlerts() {
  clearTimeout(alertsTimer);
  alertsTimer = setTimeout(() => { refreshAlerts(); refreshPlacesLive(); }, 250);
}
map.on('moveend zoomend', scheduleAlerts);
document.querySelectorAll('#filters input[data-group]').forEach((box) => {
  box.addEventListener('change', scheduleAlerts);
});
setInterval(scheduleAlerts, 30000);

// TomTom flow raster, proxied server-side; 404s harmlessly with no key.
const trafficTiles = L.tileLayer('/api/traffictile/{z}/{x}/{y}.png', {
  maxZoom: 16, minZoom: 3, opacity: 0.75,
});
document.getElementById('trafficlayer').addEventListener('change', (e) => {
  if (e.target.checked) trafficTiles.addTo(map);
  else map.removeLayer(trafficTiles);
});
document.getElementById('signblank').addEventListener('change', rebuildSigns);

// ── Address fields: autocomplete + validation ────────────────────────
// "37.35, -121.94", "37.35 -121.94", or with N/S/E/W letters: typed
// coordinates become a place without asking the geocoder.
function parseCoords(s) {
  const m = /^\s*(-?\d{1,2}(?:\.\d+)?)\s*([NS])?\s*[,\s]\s*(-?\d{1,3}(?:\.\d+)?)\s*([EW])?\s*$/i
    .exec(String(s || '').replace(/\u00b0/g, ' '));
  if (!m) return null;
  let lat = parseFloat(m[1]), lon = parseFloat(m[3]);
  if ((m[2] || '').toUpperCase() === 'S') lat = -Math.abs(lat);
  if ((m[4] || '').toUpperCase() === 'W') lon = -Math.abs(lon);
  if (!(lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180)) return null;
  return { name: lat.toFixed(5) + ', ' + lon.toFixed(5), lat, lon };
}

// Home, Work, favorites and recent destinations. Kept in this browser
// (localStorage) when signed out and as the offline copy; when signed in
// they follow the account (PlaceSync below), the same list the phone
// apps and the MCP server's get_my_places read. Shown under an empty
// address field as quick picks; each one can be removed.
const PLACES_CAP = 20;  // the account keeps 20 saved and 20 recents (watch.py)
function placeId() {
  return (window.crypto && crypto.randomUUID) ? crypto.randomUUID()
    : 'w' + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
}
const Places = {
  KEY: 'cs.places.v1',
  empty() { return { home: null, work: null, saved: [], recents: [] }; },
  load() {
    let p;
    try { p = Object.assign(this.empty(), JSON.parse(store.get(this.KEY) || '{}')); }
    catch (_) { p = this.empty(); }
    // Older copies have no ids; the account needs one per place.
    for (const r of [p.home, p.work, ...p.saved, ...p.recents]) if (r && !r.id) r.id = placeId();
    return p;
  },
  // A change made here: stored, then pushed to the account when signed in.
  save(p, removal) { store.set(this.KEY, JSON.stringify(p)); PlaceSync.changed(!!removal); },
  same(a, b) { return a && b && Math.abs(a.lat - b.lat) < 1e-4 && Math.abs(a.lon - b.lon) < 1e-4; },
  noteRecent(c) {
    if (!c || c.name === 'My location' || !isFinite(c.lat)) return;
    const p = this.load();
    const was = p.recents.find(r => this.same(r, c));
    p.recents = [{ id: was ? was.id : placeId(), name: c.name, lat: +c.lat, lon: +c.lon, at: Date.now() }]
      .concat(p.recents.filter(r => !this.same(r, c))).slice(0, PLACES_CAP);
    this.save(p);
  },
  set(kind, c) {
    const p = this.load();
    const rec = { id: placeId(), name: c.name, lat: +c.lat, lon: +c.lon, at: Date.now() };
    if (kind === 'home' || kind === 'work') p[kind] = rec;
    else {
      const was = p.saved.find(r => this.same(r, c));
      if (was) rec.id = was.id;
      p.saved = [rec].concat(p.saved.filter(r => !this.same(r, c))).slice(0, PLACES_CAP);
    }
    this.save(p);
  },
  remove(kind, c) {
    const p = this.load();
    if (kind === 'home' || kind === 'work') p[kind] = null;
    else if (kind === 'saved') p.saved = p.saved.filter(r => !this.same(r, c));
    else p.recents = p.recents.filter(r => !this.same(r, c));
    this.save(p, true);
  },
  // The account's wire shape (watch.py merge_places, the apps' Places):
  // {id, kind: home|work|saved|recent, name, lat, lon, used_at seconds}.
  toWire(p) {
    const w = (r, kind) => ({ id: r.id, kind, name: r.name || '', lat: +r.lat, lon: +r.lon,
      used_at: (r.at || 0) / 1000 });
    return [p.home && w(p.home, 'home'), p.work && w(p.work, 'work'),
      ...p.saved.map(r => w(r, 'saved')), ...p.recents.map(r => w(r, 'recent'))].filter(Boolean);
  },
  fromWire(list) {
    const p = this.empty();
    const r = (x) => ({ id: String(x.id), name: String(x.name || ''), lat: +x.lat, lon: +x.lon,
      at: Math.round((+x.used_at || 0) * 1000) });
    for (const x of list || []) {
      if (!x || !isFinite(x.lat) || !isFinite(x.lon)) continue;
      if (x.kind === 'home' || x.kind === 'work') { if (!p[x.kind]) p[x.kind] = r(x); }
      else if (x.kind === 'saved') p.saved.push(r(x));
      else if (x.kind === 'recent') p.recents.push(r(x));
    }
    p.saved.sort((a, b) => b.at - a.at);
    p.recents.sort((a, b) => b.at - a.at);
    return p;
  },
  // The account's list replaces the local copy; no push back.
  adopt(list) { store.set(this.KEY, JSON.stringify(this.fromWire(list))); },
  // The quick picks, in the order the apps use: Home, Work, favorites, recents.
  quick() {
    const p = this.load();
    const out = [];
    if (p.home) out.push({ kind: 'home', label: 'Home', c: p.home });
    if (p.work) out.push({ kind: 'work', label: 'Work', c: p.work });
    p.saved.slice(0, 5).forEach(c => out.push({ kind: 'saved', label: c.name.split(', ')[0], c }));
    p.recents.slice(0, 10).forEach(c => out.push({ kind: 'recent', label: c.name.split(', ')[0], c }));
    return out;
  },
};

// Account sync, the same protocol as the phone apps (Places.swift):
// on sign-in, one merging PUT of this browser's list, and the merged list
// comes back and replaces it. After that every change is pushed, debounced:
// additions merge, a removal replaces, but only once this browser holds
// the account's whole list, so a partial copy never wipes places saved in
// the app. Signed out, the list simply stays in this browser.
const PlaceSync = {
  signedIn: false,
  synced: false,
  timer: null,
  removal: false,
  async token() {
    try { return window.csAuth ? await window.csAuth.token() : null; } catch (_) { return null; }
  },
  async put(body) {
    const token = await this.token();
    if (!token) return null;
    try {
      const r = await fetch('/api/me/places', { method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
        body: JSON.stringify(body) });
      if (!r.ok) return null;
      const d = await r.json();
      return Array.isArray(d.places) ? d.places : null;
    } catch (_) { return null; }
  },
  async syncNow() {
    clearTimeout(this.timer); this.timer = null; this.removal = false;
    const merged = await this.put({ places: Places.toWire(Places.load()) });
    if (!merged || !this.signedIn) return;
    Places.adopt(merged);
    this.synced = true;
    placesSyncChanged();
  },
  changed(removal) {
    if (!this.signedIn) return;
    this.removal = this.removal || removal;
    clearTimeout(this.timer);
    this.timer = setTimeout(async () => {
      this.timer = null;
      const body = { places: Places.toWire(Places.load()) };
      if (this.removal && this.synced) body.replace = true;
      this.removal = false;
      const merged = await this.put(body);
      if (!merged || !this.signedIn) return;
      Places.adopt(merged);
      this.synced = true;
      placesSyncChanged();
    }, 1500);
  },
  setSignedIn(on) {
    store.set(PLACES_ACCT_KEY, on ? '1' : '');
    if (on === this.signedIn) return;
    const signingOut = this.signedIn && !on;
    this.signedIn = on;
    this.synced = false;
    if (signingOut) {
      // As the apps do: signing out drops the account's list from this
      // browser, so the next person to sign in here does not merge it in.
      // Nothing is pushed: a push now would need the token that just went.
      clearTimeout(this.timer); this.timer = null; this.removal = false;
      store.set(Places.KEY, '');
    }
    if (on) this.syncNow();
    placesSyncChanged();
  },
};
const PLACES_ACCT_KEY = 'cs-acct';
// Sign-in lives in the watch module (Firebase), loaded on demand. It
// announces every change; a browser that was signed in last time loads
// it once the map is idle, so the account's places arrive on their own.
document.addEventListener('cs-auth', (e) => PlaceSync.setSignedIn(!!(e.detail && e.detail.signedIn)));
if (store.get(PLACES_ACCT_KEY) === '1') {
  (window.requestIdleCallback || ((f) => setTimeout(f, 1500)))(() => loadWatch(), { timeout: 4000 });
}
function placesSyncChanged() {
  document.dispatchEvent(new CustomEvent('cs-places'));
}

function wireAddress(inputId, valId, suggId, withMyLocation, onPick) {
  const input = document.getElementById(inputId);
  const val = document.getElementById(valId);
  const sugg = document.getElementById(suggId);
  let seq = 0, items = [], active = -1, aborter = null, debounce = null;

  function close() { sugg.classList.remove('open'); active = -1; }
  function pick(c) {
    input.value = c.name;
    input.dataset.lat = c.lat; input.dataset.lon = c.lon;
    input.dataset.name = c.name;
    val.className = 'val ok'; val.textContent = '\u2713 ' + c.name;
    close();
    Places.noteRecent(c);
    if (onPick) onPick(c);
    if (c.approx) {
      // The row was a street match with the typed number re-attached; ask
      // the precise geocoder to interpolate the actual house position and
      // upgrade the coordinates in place. The street point stays as the
      // fallback if interpolation finds nothing.
      fetch('/api/geocode?q=' + encodeURIComponent(c.name))
        .then(r => r.json())
        .then(d => {
          const hit = (d.candidates || [])[0];
          if (hit && input.dataset.name === c.name) {
            // Upgrade the position only; the label keeps the address the
            // user picked (the geocoder's display name may drop the number).
            input.dataset.lat = hit.lat; input.dataset.lon = hit.lon;
          }
        }).catch(() => {});
    }
  }
  function useMyLocation() {
    close();
    val.className = 'val'; val.textContent = 'Finding you\u2026';
    if (!navigator.geolocation) {
      val.className = 'val err'; val.textContent = 'Location not available in this browser.';
      return;
    }
    navigator.geolocation.getCurrentPosition((pos) => {
      input.value = 'My location';
      input.dataset.lat = pos.coords.latitude;
      input.dataset.lon = pos.coords.longitude;
      input.dataset.name = 'My location';
      val.className = 'val ok';
      val.textContent = '\u2713 Using your location (\u00b1' +
        Math.round(pos.coords.accuracy) + ' m)';
    }, () => {
      val.className = 'val err';
      val.textContent = 'Location was blocked - type an address instead.';
    }, { enableHighAccuracy: false, timeout: 8000, maximumAge: 120000 });
  }
  const ICON = { home: '\u2302', work: '\u2692', saved: '\u2605', recent: '\u23F1' };
  function mylocRow() {
    const row = document.createElement('div');
    row.className = 'row myloc';
    row.textContent = '\u25CE Use my location';
    row.addEventListener('mousedown', (e) => { e.preventDefault(); useMyLocation(); });
    return row;
  }
  function render() {
    sugg.innerHTML = '';
    // Before anything is typed, "use my location" is the likeliest
    // answer and leads. Once somebody has typed a place, it is the
    // least likely one, and sitting first it caught the Enter key and
    // the first tap meant for the place they typed.
    const typing = input.value.trim().length >= 2;
    if (withMyLocation && !typing) sugg.append(mylocRow());
    // Nothing typed yet: Home, Work, favorites and recent destinations.
    if (!items.length && input.value.trim().length < 2) {
      Places.quick().forEach((q) => {
        const row = document.createElement('div');
        row.className = 'row quick ' + q.kind;
        const b = document.createElement('b'); b.textContent = ICON[q.kind] + ' ' + q.label;
        const small = document.createElement('small');
        small.textContent = q.kind === 'home' || q.kind === 'work' ? q.c.name : q.c.name.split(', ').slice(1).join(', ');
        const x = document.createElement('button');
        x.type = 'button'; x.className = 'rm'; x.title = 'Remove'; x.setAttribute('aria-label', 'Remove ' + q.label); x.textContent = '\u00d7';
        x.addEventListener('mousedown', (e) => { e.preventDefault(); e.stopPropagation(); Places.remove(q.kind, q.c); render(); });
        row.append(b, small, x);
        row.addEventListener('mousedown', (e) => { e.preventDefault(); pick(Object.assign({}, q.c)); });
        sugg.append(row);
      });
    }
    items.forEach((c, i) => {
      const row = document.createElement('div');
      row.className = 'row' + (i === active ? ' active' : '');
      const parts = c.name.split(', ');
      const b = document.createElement('b'); b.textContent = parts[0];
      const small = document.createElement('small');
      small.textContent = parts.slice(1).join(', ');
      row.append(b, small);
      row.addEventListener('mousedown', (e) => { e.preventDefault(); pick(c); });
      sugg.append(row);
    });
    if (withMyLocation && typing) sugg.append(mylocRow());
    if (sugg.children.length) sugg.classList.add('open'); else close();
  }
  async function fetchSuggestions() {
    const q = input.value.trim();
    if (q.length < 2 || q === input.dataset.name) { items = []; render(); return; }
    const coord = parseCoords(q);
    if (coord) { items = [coord]; active = 0; render(); return; }
    const mine = ++seq;
    if (aborter) aborter.abort();
    aborter = new AbortController();
    try {
      const c = map.getCenter();
      const res = await fetch('/api/suggest?q=' + encodeURIComponent(q) +
        '&lat=' + c.lat.toFixed(2) + '&lon=' + c.lng.toFixed(2),
        { signal: aborter.signal });
      const data = await res.json();
      if (mine !== seq) return;
      items = data.suggestions || [];
      active = -1;
      render();
    } catch (e) { /* aborted or offline; keep whatever is shown */ }
  }
  input.addEventListener('input', () => {
    delete input.dataset.lat; delete input.dataset.name;
    val.textContent = ''; val.className = 'val';
    clearTimeout(debounce);
    debounce = setTimeout(fetchSuggestions, 250);
  });
  input.addEventListener('focus', () => {
    if (withMyLocation || items.length || Places.quick().length) render();
  });
  input.addEventListener('blur', () => setTimeout(close, 150));
  input.addEventListener('keydown', (e) => {
    if (!sugg.classList.contains('open')) return;
    const max = items.length - 1;
    if (e.key === 'ArrowDown') { e.preventDefault(); active = Math.min(active + 1, max); render(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); active = Math.max(active - 1, -1); render(); }
    else if (e.key === 'Enter') {
      if (active >= 0) { e.preventDefault(); pick(items[active]); }
      else close();
    }
    else if (e.key === 'Escape') close();
  });

  let vseq = 0;
  async function validate() {
    const q = input.value.trim();
    if (input.dataset.name === q && input.dataset.lat) return;  // picked
    delete input.dataset.lat;
    if (!q) { val.textContent = ''; val.className = 'val'; return; }
    const coord = parseCoords(q);
    if (coord) { pick(coord); return; }
    const mine = ++vseq;
    val.className = 'val'; val.textContent = 'Checking address\u2026';
    try {
      const res = await fetch('/api/geocode?q=' + encodeURIComponent(q));
      const data = await res.json();
      if (mine !== vseq) return;
      const cands = data.candidates || [];
      if (!cands.length) {
        val.className = 'val err';
        val.textContent = "Couldn't find that place - try adding a city.";
        return;
      }
      if (cands.length === 1) { pick(cands[0]); return; }
      val.className = 'val'; val.innerHTML = '';
      const sel = document.createElement('select');
      sel.append(new Option('Which one did you mean?', '', true, true));
      sel.options[0].disabled = true;
      cands.forEach((c, i) => sel.append(new Option(c.name, String(i))));
      sel.addEventListener('change', () => pick(cands[+sel.value]));
      val.append(sel);
    } catch (e) {
      if (mine !== vseq) return;
      val.className = 'val err'; val.textContent = 'Address check failed - try again.';
    }
  }
  input.addEventListener('change', () => setTimeout(validate, 200));
  return { input, val, validate, pick };
}
const fromF = wireAddress('from', 'fromval', 'fromsugg', true);
const toF = wireAddress('to', 'toval', 'tosugg', false);

// ── Find anything on the map ─────────────────────────────────────────
// The box over the map takes a place, an address or coordinates and
// drops a pin with "Navigate here". The From/To planner stays for
// trips that start somewhere else.
let findPin = null;
const findF = wireAddress('find', 'findval', 'findsugg', false, showFound);
const findClear = document.getElementById('findclear');
function clearFound() {
  if (findPin) { map.removeLayer(findPin); findPin = null; }
  findF.input.value = '';
  delete findF.input.dataset.lat; delete findF.input.dataset.name;
  findF.val.textContent = ''; findF.val.className = 'val';
  findClear.hidden = true;
}
function showFound(c) {
  if (findPin) map.removeLayer(findPin);
  const at = [c.lat, c.lon];
  findPin = L.marker(at, {
    icon: L.divIcon({ className: 'findpin', html: '<i></i>', iconSize: [18, 18], iconAnchor: [9, 9] }),
    zIndexOffset: 900,
  }).addTo(map);
  findClear.hidden = false;
  const box = document.createElement('div');
  box.className = 'findpop';
  const parts = c.name.split(', ');
  const name = document.createElement('b'); name.textContent = parts[0];
  const sub = document.createElement('small'); sub.textContent = parts.slice(1).join(', ');
  const nav = document.createElement('button');
  nav.type = 'button'; nav.className = 'planbtn'; nav.textContent = 'Navigate here';
  nav.addEventListener('click', () => navigateTo(c));
  const save = document.createElement('div');
  save.className = 'saverow';
  [['home', 'Save as Home'], ['work', 'Save as Work'], ['saved', 'Save to favorites']].forEach(([k, label]) => {
    const btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'linkbtn'; btn.textContent = label;
    btn.addEventListener('click', () => { Places.set(k, c); btn.textContent = 'Saved'; btn.disabled = true; renderPlaces(); });
    save.append(btn);
  });
  box.append(name, sub, nav, save);
  findPin.bindPopup(box, { maxWidth: 280 });
  map.flyTo(at, Math.max(map.getZoom(), 14), { duration: 0.7 });
  setTimeout(() => findPin && findPin.openPopup(), 750);
  findF.input.blur();   // the popup folds the phone sheet by itself
  placesPicked(c);      // Your places asked for this pick: save it there
}
// Into the planner: the pin is the destination; the start is the
// driver's own location unless From already says otherwise.
function navigateTo(c) {
  toF.pick(c);
  setTool('route', { toggle: false, reveal: true });
  if (fromF.input.dataset.lat) planbtn.click();
  else fromF.input.focus();
}
findClear.addEventListener('click', clearFound);
findF.input.addEventListener('keydown', (e) => {
  if (e.key !== 'Enter') return;
  // Nothing chosen from the list: ask the geocoder for the typed text.
  setTimeout(() => {
    if (!findF.input.dataset.lat && findF.input.value.trim()) findF.validate();
  }, 0);
});

// ── Routing with turn-by-turn directions ─────────────────────────────
function valhallaTripToRoute(trip) {
  // Name the route by the road you spend the longest stretch on.
  let best = null;
  for (const m of trip.legs.flatMap(l => l.maneuvers || [])) {
    if ((m.street_names || []).length && (!best || m.length > best.length)) {
      best = m;
    }
  }
  const perUnit = trip.units === 'kilometers' ? 1000 : 1609.344;
  return {
    latlngs: trip.legs.flatMap(l => decodePolyline6(l.shape)),
    distance: trip.summary.length * perUnit,
    duration: trip.summary.time,
    via: best ? best.street_names[0].split(';')[0] : '',
    steps: trip.legs.flatMap(l => l.maneuvers || []).map(s => ({
      text: s.instruction.replace(/\.$/, ''), miles: s.length,
    })),
  };
}
// The server plans with our own knowledge (full closures excluded,
// candidates ranked by what lies on them, one-tap presets) and holds
// the routing key and the daily budget; past the budget the page says
// the route servers are busy rather than route around it.
let routePreset = 'fastest';
let planNote = null;
async function serverDirections(points, preset) {
  const res = await fetch('/api/route', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ locations: points.map(p => ({ lat: p[0], lon: p[1] })),
      preset, units: csUnits.get() === 'km' ? 'kilometers' : 'miles' }),
    signal: AbortSignal.timeout(12000),
  });
  if (!res.ok) return null;
  const data = await res.json();
  if (!data.routes || !data.routes.length) return null;
  planNote = data.note || null;
  return data.routes.slice(0, 3).map((r) => Object.assign(
    valhallaTripToRoute(r.trip),
    { hassles: r.hassles || [], penalty: r.penalty_min || 0 }));
}
async function anyDirections(points) {
  planNote = null;
  try { return await serverDirections(points, routePreset); } catch (e) { return null; }
}
document.getElementById('routepresets').addEventListener('click', async (e) => {
  const btn = e.target.closest('button[data-preset]');
  if (!btn || btn.dataset.preset === routePreset) return;
  routePreset = btn.dataset.preset;
  document.querySelectorAll('#routepresets button').forEach((b) => {
    b.classList.toggle('on', b === btn);
  });
  if (lastEnds) await replanVias();
});

const layerRoute = L.layerGroup().addTo(map);
let plannedRoute = null;

function downloadFile(name, mime, text) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: mime }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 3000);
}
function tripSlug() {
  const clean = (s) => (s || '').split(',')[0].replace(/[^A-Za-z0-9]+/g, '-');
  return clean(plannedRoute.fromName) + '-to-' + clean(plannedRoute.toName);
}
document.getElementById('gpxbtn').addEventListener('click', () => {
  if (!plannedRoute) return;
  const pts = plannedRoute.route.latlngs.map((p) =>
    '<trkpt lat="' + p[0].toFixed(5) + '" lon="' + p[1].toFixed(5) + '"/>')
    .join('\n      ');
  downloadFile(tripSlug() + '.gpx', 'application/gpx+xml',
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<gpx version="1.1" creator="CommuteScout" xmlns="http://www.topografix.com/GPX/1/1">\n' +
    '  <trk><name>' + tripSlug() + '</name>\n    <trkseg>\n      ' +
    pts + '\n    </trkseg>\n  </trk>\n</gpx>\n');
});
document.getElementById('kmlbtn').addEventListener('click', () => {
  if (!plannedRoute) return;
  const coords = plannedRoute.route.latlngs.map((p) =>
    p[1].toFixed(5) + ',' + p[0].toFixed(5) + ',0').join(' ');
  downloadFile(tripSlug() + '.kml', 'application/vnd.google-earth.kml+xml',
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>' +
    '<name>' + tripSlug() + '</name><Placemark><LineString><coordinates>' +
    coords + '</coordinates></LineString></Placemark></Document></kml>\n');
});
function showLinkInline(after, url) {
  let box = after.parentNode.querySelector('.linkinline');
  if (!box) {
    box = document.createElement('input');
    box.className = 'linkinline';
    box.readOnly = true;
    box.setAttribute('aria-label', 'Link to copy');
    box.style.cssText = 'display:block;width:100%;margin-top:6px;font:inherit;padding:6px 8px;';
    after.insertAdjacentElement('afterend', box);
  }
  box.value = url;
  box.focus();
  box.select();
}
document.getElementById('sharebtn').addEventListener('click', async () => {
  if (!plannedRoute) return;
  const r = plannedRoute.route;
  const step = Math.max(1, Math.floor(r.latlngs.length / 450));
  const btn = document.getElementById('sharebtn');
  btn.textContent = 'Creating\u2026';
  try {
    const res = await fetch('/api/trip', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        from_name: plannedRoute.fromName, to_name: plannedRoute.toName,
        miles: r.distance / 1609.344, minutes: r.duration / 60,
        via: r.via || '',
        latlngs: r.latlngs.filter((_, i) => i % step === 0 ||
          i === r.latlngs.length - 1),
        steps: (r.steps || []).map((s) => ({ text: s.text, miles: s.miles })),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'could not create link');
    let copied = true;
    await navigator.clipboard.writeText(data.url).catch(() => { copied = false; });
    btn.textContent = copied ? 'Link copied!' : 'Share link';
    // A browser that refuses the clipboard (no user gesture, a locked
    // down profile) gets the link on the page instead. Never a native
    // prompt: that blocks the whole tab until somebody dismisses it.
    if (!copied) showLinkInline(btn, data.url);
    setTimeout(() => { btn.textContent = 'Share link'; }, 2500);
  } catch (e) {
    btn.textContent = 'Share failed';
    btn.title = e.message;
    setTimeout(() => { btn.textContent = 'Share link'; btn.title = ''; }, 4000);
  }
});
let plannedRoutes = [];
const planbtn = document.getElementById('planbtn');
let viaPoints = [];
let lastEnds = null;
let suppressPinOnce = false;

let viaManual = false;

let itinHl = null;
function dropItinHl() {
  if (itinHl) { map.removeLayer(itinHl); itinHl = null; }
}

function renderViaChips() {
  dropItinHl();
  const box = document.getElementById('viachips');
  box.innerHTML = '';
  if (!lastEnds) return;
  const mkBtn = (label, title, cls, fn) => {
    const b = document.createElement('button');
    b.type = 'button'; b.textContent = label; b.title = title;
    if (cls) b.className = cls;
    b.addEventListener('click', fn);
    return b;
  };
  // Google Maps grammar: hollow circle for the start, numbered gray dots
  // for stops, a red pin for the destination, dotted connector between.
  const legRow = (kind, badgeText, name) => {
    const row = document.createElement('div');
    row.className = 'leg ' + kind;
    const badge = document.createElement('span');
    badge.className = 'badge'; badge.textContent = badgeText;
    const nm = document.createElement('span');
    nm.className = 'legname'; nm.textContent = name;
    row.append(badge, nm);
    return row;
  };
  box.append(legRow('origin', '',
    (fromF.input.dataset.name || 'Start').split(',')[0]));
  viaPoints.forEach((v, i) => {
    const row = legRow('stop', String(i + 1),
      'Stop \u00b7 ' + v[0].toFixed(3) + ', ' + v[1].toFixed(3));
    row.draggable = true;
    row.addEventListener('dragstart', (ev) => {
      ev.dataTransfer.setData('text/plain', String(i));
      ev.dataTransfer.effectAllowed = 'move';
      row.classList.add('dragging');
    });
    row.addEventListener('dragend', () => row.classList.remove('dragging'));
    row.addEventListener('dragover', (ev) => { ev.preventDefault(); });
    row.addEventListener('drop', async (ev) => {
      ev.preventDefault();
      const from = Number(ev.dataTransfer.getData('text/plain'));
      if (!Number.isInteger(from) || from === i) return;
      viaManual = true;
      const [moved] = viaPoints.splice(from, 1);
      viaPoints.splice(i, 0, moved);
      await replanVias();
    });
    row.addEventListener('mouseenter', () => {
      dropItinHl();
      itinHl = L.circleMarker(v, { radius: 13, color: '#2f81f7',
        weight: 3, fill: false }).addTo(map);
    });
    row.addEventListener('mouseleave', dropItinHl);
    row.append(mkBtn('\u00d7', 'Remove this stop', 'rm', async () => {
      viaPoints.splice(i, 1);
      await replanVias();
    }));
    box.append(row);
  });
  box.append(legRow('dest', '',
    (toF.input.dataset.name || 'End').split(',')[0]));
  if (viaPoints.length < 5) {
    const add = document.createElement('button');
    add.type = 'button'; add.className = 'addstop';
    add.innerHTML = '<span class="plus">+</span> Add stop \u00b7 click the map';
    add.classList.toggle('armed', pickMode === 'via');
    add.addEventListener('click', () => setPickMode('via'));
    box.append(add);
  }
}

function clearRoute() {
  routeGen += 1;
  dropItinHl();
  clearPickMarks();
  if (condHighlight) { map.removeLayer(condHighlight); condHighlight = null; }
  viaPoints = []; viaManual = false; lastEnds = null;
  plannedRoute = null; plannedRoutes = [];
  setPlanned(false);
  layerRoute.clearLayers();
  renderViaChips();
  for (const id of ['routesum', 'routealts', 'routecond', 'steps']) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = '';
  }
  const wrap = document.getElementById('routeasks-wrap');
  if (wrap) wrap.style.display = 'none';
  const pw = document.getElementById('printwrap');
  if (pw) pw.style.display = 'none';
  hideRouteStrip();
}
document.getElementById('clearroutebtn')
  .addEventListener('click', clearRoute);

// ── The planned trip, board #11: a header, the alternatives as chips,
// then the route item by item. The arrow goes back to the fields.
const planPane = document.getElementById('pane-plan');
function setPlanned(on) {
  planPane.classList.toggle('planned', !!on);
  document.getElementById('rhead').hidden = !on;
  if (!on) setLeaveOpen(false);
}
function setLeaveOpen(open) {
  const b = document.getElementById('rleave');
  b.setAttribute('aria-expanded', open ? 'true' : 'false');
  planPane.classList.toggle('leaveopen', !!open);
}
function updateRouteHead() {
  if (!plannedRoute) return;
  const r = plannedRoute.route;
  const free = Math.round(r.duration / 60);
  const mins = plannedRoute.trafficMins || free;
  const slower = mins - free;
  document.getElementById('rhtitle').textContent =
    placeLabel(plannedRoute.fromC) + ' to ' + placeLabel(plannedRoute.toC);
  const meta = document.getElementById('rhmeta');
  meta.innerHTML = '<b' + (slower >= 2 ? ' class="late"' : '') + '>' + minsTxt(mins) + '</b> · ' +
    csUnits.fmt(r.distance / 1000, 1) +
    (slower >= 2 ? ' · <span class="late">' + slower + ' min slower</span>'
      : plannedRoute.flow ? ' · traffic flowing' : '');
  const dep = departEpoch();
  document.getElementById('rleavetxt').textContent = dep
    ? 'Leave ' + clockTxtMs(dep * 1000) : 'Leave now';
}
// Recent trips keep the newest time measured for the drive.
function noteTrip() {
  if (!plannedRoute) return;
  const r = plannedRoute.route;
  Trips.note({ a: plannedRoute.fromC, b: plannedRoute.toC,
    mins: plannedRoute.trafficMins || Math.round(r.duration / 60),
    km: r.distance / 1000, at: Date.now() });
}
document.getElementById('rback').addEventListener('click', () => {
  planPane.classList.remove('planned');
  document.getElementById('rhead').hidden = true;
  document.getElementById('to').focus();
});
document.getElementById('rleave').addEventListener('click', () => {
  const open = document.getElementById('rleave').getAttribute('aria-expanded') !== 'true';
  setLeaveOpen(open);
  if (open) document.getElementById('departmode').focus();
});
// Popups pan clear of the floating panel (and on a phone, the search).
function syncPopupPad() {
  const pad = mapPad();
  L.Popup.prototype.options.autoPanPaddingTopLeft = L.point(pad.paddingTopLeft[0] - 16, pad.paddingTopLeft[1] - 16);
  L.Popup.prototype.options.autoPanPaddingBottomRight = L.point(pad.paddingBottomRight[0] - 16, pad.paddingBottomRight[1] - 16);
}
document.addEventListener('cs-tool', () => setTimeout(syncPopupPad, 80));
window.addEventListener('resize', () => setTimeout(syncPopupPad, 80));
setTimeout(syncPopupPad, 0);
// Map padding that keeps a fitted area clear of the floating panel (and
// on a phone, of the sheet and the search above it).
function mapPad() {
  const card = map.getContainer().getBoundingClientRect();
  if (isPhone()) {
    const sheet = document.getElementById('panel').getBoundingClientRect();
    return { paddingTopLeft: [24, 120], paddingBottomRight: [24, Math.max(24, card.bottom - sheet.top + 24)] };
  }
  const p = document.getElementById('panel').getBoundingClientRect();
  const left = shellEl.classList.contains('nopanel') ? 48 : Math.max(48, p.right - card.left + 32);
  return { paddingTopLeft: [left, 72], paddingBottomRight: [72, 72] };
}

// ── Depart at: pick a future time, the conditions list re-reads every
// item's Caltrans schedule against it. (Historical predictions will
// plug in here once the event archive is deep enough.) ───────────────
const departMode = document.getElementById('departmode');
const departAt = document.getElementById('departat');
function localStamp(d) {
  const p = (n) => String(n).padStart(2, '0');
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) +
    'T' + p(d.getHours()) + ':' + p(d.getMinutes());
}
departMode.addEventListener('change', () => {
  const later = departMode.value === 'later';
  departAt.classList.toggle('hidden', !later);
  if (later && !departAt.value) {
    const d = new Date(Date.now() + 3600 * 1000);
    d.setMinutes(0, 0, 0);
    departAt.min = localStamp(new Date());
    departAt.value = localStamp(d);
  }
  if (lastRouteLL) renderRouteConditions(lastRouteLL);
  updateRouteHead();
});
departAt.addEventListener('change', () => {
  if (lastRouteLL) renderRouteConditions(lastRouteLL);
  updateRouteHead();
});

function viaOrdered(routeLatlngs) {
  // Waypoints keep their order along the current route so dragging a
  // second bend never crosses the wires with the first.
  const frac = (pt) => {
    let best = 0, bestD = Infinity;
    for (let i = 0; i < routeLatlngs.length; i += 3) {
      const d = Math.hypot(routeLatlngs[i][0] - pt[0],
        routeLatlngs[i][1] - pt[1]);
      if (d < bestD) { bestD = d; best = i; }
    }
    return best;
  };
  return [...viaPoints].sort((x, y) => frac(x) - frac(y));
}

async function planWith(points, a, b) {
  planbtn.disabled = true; planbtn.textContent = 'Planning\u2026';
  try {
    const routes = await anyDirections(points);
    if (!routes || !routes.length) {
      document.getElementById('routesum').textContent =
        'Route servers are busy - try again in a moment.';
      document.getElementById('routealts').innerHTML = '';
      document.getElementById('printwrap').style.display = 'block';
      return;
    }
    plannedRoutes = routes;
    renderRouteAlts(0, a, b);
  } finally {
    planbtn.disabled = false; planbtn.textContent = 'Plan route';
  }
}

async function replanVias() {
  if (!lastEnds) return;
  const base = plannedRoute ? plannedRoute.route.latlngs : [];
  const vias = viaPoints.length
    ? (viaManual ? viaPoints : viaOrdered(base)) : [];
  viaPoints = vias;
  await planWith([lastEnds.a, ...vias, lastEnds.b],
    lastEnds.a, lastEnds.b);
  renderViaChips();
}

planbtn.addEventListener('click', async () => {
  if (!fromF.input.dataset.lat) await fromF.validate();
  if (!toF.input.dataset.lat) await toF.validate();
  if (!fromF.input.dataset.lat || !toF.input.dataset.lat) return;
  const a = [+fromF.input.dataset.lat, +fromF.input.dataset.lon];
  const b = [+toF.input.dataset.lat, +toF.input.dataset.lon];
  viaPoints = []; viaManual = false;
  // lastEnds must be set BEFORE rendering: renderViaChips() early-returns
  // without it, which used to blank the itinerary on the first plan.
  lastEnds = { a, b };
  renderViaChips();
  await planWith([a, b], a, b);
});

// Click an empty spot on the map to route from or to it, like the big
// guys do.
const pinPopup = L.popup({ closeButton: true, autoClose: true });
function setPinField(field, ll) {
  const name = 'Pin ' + ll.lat.toFixed(3) + ' / ' + ll.lng.toFixed(3);
  field.input.value = name;
  field.input.dataset.lat = ll.lat;
  field.input.dataset.lon = ll.lng;
  field.input.dataset.name = name;
  const val = document.getElementById(
    field.input.id === 'from' ? 'fromval' : 'toval');
  val.className = 'val ok'; val.textContent = '\u2713 ' + name;
  map.closePopup(pinPopup);
  if (fromF.input.dataset.lat && toF.input.dataset.lat) planbtn.click();
}
// ── Pick-on-map: a sidebar "Pick on map" button arms which route point
// the next single map click sets. Without an armed mode, map clicks no
// longer drop a from/to/stop chooser on every click. ───────────────────
let pickMode = null;  // 'from' | 'to' | 'via' | null
const pickHint = document.getElementById('pickhint');
const pickBtns = {
  from: document.getElementById('pickfrom'),
  to: document.getElementById('pickto'),
  via: document.getElementById('viapickbtn'),
};
const PICK_LABEL = {
  from: 'Click the map to set your start',
  to: 'Click the map to set your destination',
  via: 'Click the map to add a stop',
  report: 'Click the map where it is',
};
function setPickMode(mode) {
  pickMode = (pickMode === mode) ? null : mode;
  for (const [k, btn] of Object.entries(pickBtns)) {
    if (btn) btn.classList.toggle('armed', pickMode === k);
  }
  document.querySelectorAll('.addstop').forEach((b) =>
    b.classList.toggle('armed', pickMode === 'via'));
  document.querySelectorAll('[data-act="report"]').forEach((b) => b.classList.toggle('armed', pickMode === 'report'));
  map.getContainer().style.cursor = pickMode ? 'crosshair' : '';
  if (pickMode) {
    pickHint.textContent = PICK_LABEL[pickMode]; pickHint.hidden = false;
    if (isPhone()) setSheet('peek');
  }
  else { pickHint.hidden = true; }
}

// Every pick drops a marker at the chosen spot immediately, so the point
// is visible before (and independent of) any route render. Google-style
// grammar: hollow circle for the start, red pin for the destination,
// small gray dot for stops.
const pickMarks = { from: null, to: null, via: L.layerGroup() };
pickMarks.via.addTo(map);
function dropPickMark(mode, latlng) {
  const mk = (opts) => L.circleMarker(latlng, Object.assign({
    pane: 'markerPane', weight: 3, fillOpacity: 1 }, opts));
  if (mode === 'from') {
    if (pickMarks.from) map.removeLayer(pickMarks.from);
    pickMarks.from = mk({ radius: 7, color: '#0f1c2b', fillColor: '#fff' }).addTo(map);
  } else if (mode === 'to') {
    if (pickMarks.to) map.removeLayer(pickMarks.to);
    pickMarks.to = L.marker(latlng, {
      icon: L.divIcon({ className: '', iconSize: [18, 18], iconAnchor: [9, 16],
        html: '<div style="width:15px;height:15px;border-radius:50% 50% 50% 0;' +
              'transform:rotate(-45deg);background:#d64545;' +
              'border:2.5px solid #fffdf7"></div>' }),
    }).addTo(map);
  } else {
    pickMarks.via.addLayer(mk({ radius: 5, color: '#fff', weight: 2,
      fillColor: '#5b6b7d' }));
  }
}
function clearPickMarks() {
  if (pickMarks.from) { map.removeLayer(pickMarks.from); pickMarks.from = null; }
  if (pickMarks.to) { map.removeLayer(pickMarks.to); pickMarks.to = null; }
  pickMarks.via.clearLayers();
}
pickBtns.from.addEventListener('click', () => setPickMode('from'));
pickBtns.to.addEventListener('click', () => setPickMode('to'));
if (pickBtns.via) pickBtns.via.addEventListener('click', () => setPickMode('via'));
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && pickMode) setPickMode(null);
});

function clickNearRoute(latlng) {
  if (!plannedRoute || !lastEnds) return false;
  const pts = plannedRoute.route.latlngs;
  const c = map.latLngToLayerPoint(latlng);
  const step = Math.max(1, Math.floor(pts.length / 250));
  let prev = map.latLngToLayerPoint(pts[0]);
  for (let i = step; i < pts.length; i += step) {
    const cur = map.latLngToLayerPoint(pts[i]);
    const dx = cur.x - prev.x, dy = cur.y - prev.y;
    const seg2 = dx * dx + dy * dy;
    const t = seg2 ? Math.max(0, Math.min(1,
      ((c.x - prev.x) * dx + (c.y - prev.y) * dy) / seg2)) : 0;
    const px = prev.x + t * dx - c.x, py = prev.y + t * dy - c.y;
    if (px * px + py * py < 26 * 26) return true;
    prev = cur;
  }
  return false;
}

map.on('click', async (e) => {
  // A reshape drag ends with a synthetic map click; swallow it.
  if (suppressPinOnce) { suppressPinOnce = false; return; }
  // Map clicks only set route points when a sidebar "Pick on map" button
  // has armed a target. Without that, clicking the map does nothing here
  // (it no longer drops a from/to/stop chooser on every click).
  if (!pickMode) return;
  const mode = pickMode;
  setPickMode(null);
  if (mode === 'report') { openReportForm(await snapForReport(e.latlng), e.latlng); return; }
  dropPickMark(mode, e.latlng);
  if (mode === 'from') { setPinField(fromF, e.latlng); return; }
  if (mode === 'to') { setPinField(toF, e.latlng); return; }
  if (mode === 'via' && lastEnds && viaPoints.length < 5) {
    viaPoints.push([e.latlng.lat, e.latlng.lng]);
    await replanVias();
  }
});

// ── Community reports (Flare) ────────────────────────────────────
// One control on the map arms a pick; the click opens the form at that
// spot. Reporting needs a signed-in account, which the watch module
// owns: it exposes csAuth.token() once loaded.
const REPORT_KINDS = [
  ['POLICE_VISIBLE', 'Police'], ['CRASH_MAJOR', 'Crash'],
  ['HAZARD_ON_ROAD', 'Hazard on road'], ['HAZARD_SHOULDER_CAR', 'Car on shoulder'],
  ['ROAD_CLOSED', 'Road closed'], ['LANE_CLOSED', 'Lane closed'],
  ['JAM_HEAVY', 'Traffic jam'], ['WEATHER_FOG', 'Fog or weather'],
  ['WEATHER_FLOOD', 'Flooding'], ['WEATHER_ICE', 'Ice or snow'],
  ['CHAINS_REQUIRED', 'Chains required'], ['CHAINS_NOT_REQUIRED', 'Chains not needed'],
  ['CAMERA_ISSUE', 'Camera issue'], ['MAP_ISSUE', 'Map issue'],
];
// Report lives in the rail's More group and the command palette; the
// map itself carries no Report button (board #3).
function startReport() {
  loadWatch();  // sign-in state, so the form can send
  setPickMode(pickMode === 'report' ? null : 'report');
}
async function authToken() {
  const w = await loadWatch();
  if (!w || !window.csAuth) return null;
  return window.csAuth.token();
}
async function flarePost(path, body) {
  const token = await authToken();
  if (!token) return { error: 'signin' };
  const res = await fetch(path, { method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
    body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return { error: data.error || ('failed (' + res.status + ')') };
  return data;
}
// A report placed near a road lands on it (the server asks the router
// for the nearest road within 60 m); further away it stays put. The
// form always offers the exact click back.
async function snapForReport(latlng) {
  try {
    const r = await fetch('/api/snap?lat=' + latlng.lat.toFixed(6) + '&lon=' + latlng.lng.toFixed(6));
    const d = await r.json();
    if (d && d.snapped) return Object.assign(L.latLng(d.lat, d.lon), { road: d.road || null });
  } catch (e) { /* the click itself is the fallback */ }
  return latlng;
}
function openReportForm(latlng, exact) {
  let kind = null;
  const box = document.createElement('div');
  box.className = 'reportform';
  box.innerHTML = '<div class="k"><i style="--dot:' + GROUP_DOT.plugin + '"></i>REPORT HERE</div>' +
    '<div class="kinds"></div><input type="text" maxlength="200" placeholder="What do you see? (optional)">' +
    '<div class="row"><button type="button" class="detbtn send">Send report</button>' +
    '<button type="button" class="detbtn cancel">Cancel</button></div><div class="note"></div>';
  const kinds = box.querySelector('.kinds');
  for (const [k, label] of REPORT_KINDS) {
    const b = document.createElement('button');
    b.type = 'button'; b.textContent = label; b.dataset.kind = k;
    b.addEventListener('click', () => {
      kind = k;
      kinds.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b));
    });
    kinds.appendChild(b);
  }
  const note = box.querySelector('.note');
  const pop = L.popup({ maxWidth: 320, closeOnClick: false }).setLatLng(latlng).setContent(box).openOn(map);
  if (exact && latlng.road !== undefined && (latlng.lat !== exact.lat || latlng.lng !== exact.lng)) {
    const where = document.createElement('div');
    where.className = 'where';
    where.innerHTML = 'On <b></b>. <button type="button" class="linkbtn">Use the exact spot</button>';
    where.querySelector('b').textContent = latlng.road || 'the road';
    where.querySelector('button').addEventListener('click', () => {
      latlng = exact; pop.setLatLng(exact);
      where.textContent = 'At the exact spot you clicked.';
    });
    box.insertBefore(where, kinds);
  }
  box.querySelector('.cancel').addEventListener('click', () => map.closePopup(pop));
  box.querySelector('.send').addEventListener('click', async () => {
    if (!kind) { note.textContent = 'Pick what you see first.'; return; }
    note.textContent = 'Sending\u2026';
    const sw = pluginSwitches();
    const r = await flarePost('/api/flare/report', { kind, lat: latlng.lat, lon: latlng.lng,
      description: box.querySelector('input').value.trim(),
      plugins_off: sw.off, plugins_on: sw.on });
    if (r.error === 'signin') {
      note.innerHTML = 'Sign in to report. <button type="button" class="detbtn" id="reportsignin">Open Watch</button>';
      note.querySelector('#reportsignin').addEventListener('click', () => {
        map.closePopup(pop); setTool('watch', { toggle: false, reveal: true });
      });
      return;
    }
    if (r.error) { note.textContent = r.error; return; }
    note.textContent = 'Sent. It shows on the map within a minute' +
      (r.forwarded && r.forwarded.length ? ' and went to ' + r.forwarded.length + ' source(s).' : '.');
    box.querySelector('.send').disabled = true;
    setTimeout(() => map.closePopup(pop), 2500);
  });
}
// Plugin popups get "Still there" and "Not there" votes.
map.on('popupopen', (e) => {
  const src = (e.popup && e.popup.__m) ? e.popup : (e.popup && e.popup._source);
  const m = src && src.__m;
  const g = src && src.__g;
  const el = e.popup.getElement();
  const card = el && el.querySelector('.p2, .pop');
  if (g !== 'plugin' || !m || !m.id || !card || card.querySelector('.confirmrow')) return;
  const row = document.createElement('div');
  row.className = 'confirmrow';
  for (const [vote, label] of [['up', 'Still there'], ['gone', 'Not there']]) {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'detbtn'; b.textContent = label;
    b.addEventListener('click', async () => {
      row.querySelectorAll('button').forEach((x) => { x.disabled = true; });
      const r = await flarePost('/api/flare/confirm', { alert_id: m.id, vote });
      const msgEl = document.createElement('div');
      msgEl.className = 'note';
      if (r.error === 'signin') msgEl.textContent = 'Sign in from the Watch tool to vote.';
      else if (r.error) msgEl.textContent = r.error;
      else msgEl.textContent = r.hidden ? 'Thanks. Enough people said it is gone; it is off the map.' : 'Thanks, noted.';
      row.after(msgEl);
      if (r.error) row.querySelectorAll('button').forEach((x) => { x.disabled = false; });
    });
    row.appendChild(b);
  }
  card.appendChild(row);
});

function mobileReveal(el) {
  if (window.matchMedia('(max-width: 960px)').matches && el) {
    setTimeout(() => {
      const y = el.getBoundingClientRect().top + window.scrollY - 8;
      window.scrollTo({ top: y, behavior: 'smooth' });
    }, 350);
  }
}

function renderRouteAlts(chosen, a, b) {
  const alts = document.getElementById('routealts');
  alts.innerHTML = '';
  if (plannedRoutes.length > 1) {
    // Chips, board #11: the quickest is "Fastest", the others by the
    // road that sets them apart, each with its drive time.
    const quickest = plannedRoutes.reduce((q, r, i) => r.duration < plannedRoutes[q].duration ? i : q, 0);
    plannedRoutes.forEach((r, i) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = i === chosen ? 'on' : '';
      btn.setAttribute('aria-pressed', i === chosen ? 'true' : 'false');
      const bEl = document.createElement('b');
      bEl.textContent = i === quickest ? 'Fastest' : r.via ? 'Via ' + r.via.split(',')[0] : 'Route ' + (i + 1);
      const sm = document.createElement('small');
      sm.textContent = Math.round(r.duration / 60) + ' min';
      sm.title = csUnits.fmt(r.distance / 1000, 0);
      btn.append(bEl, document.createTextNode(' · '), sm);
      if (r.hassles) {
        const em = document.createElement('em');
        em.textContent = r.hassles.length
          ? 'On it: ' + r.hassles.map((h) => h.label).join(', ')
          : 'Clear right now';
        em.className = r.hassles.length ? 'warn' : '';
        btn.append(em);
      }
      btn.addEventListener('click', () => renderRouteAlts(i, a, b));
      alts.append(btn);
    });
  }
  // What is on the chosen route, under the chips (the chips carry only
  // name and time).
  const pick = plannedRoutes[chosen];
  if (pick && pick.hassles && pick.hassles.length) {
    const p = document.createElement('p');
    p.className = 'althassle';
    p.textContent = 'On this route: ' + pick.hassles.map((h) => h.label).join(', ');
    alts.append(p);
  }
  showRoute(plannedRoutes[chosen],
    plannedRoutes.filter((_, i) => i !== chosen), a, b);
  const note = document.getElementById('plannote');
  note.textContent = planNote || '';
  note.hidden = !planNote;
}

function flowColor(ratio) {
  if (ratio == null) return '#0b1f33';
  if (ratio >= 0.8) return '#2f9e6e';
  if (ratio >= 0.55) return '#e8a13c';
  return '#d64545';
}

async function colorRouteByTraffic(route, baseLine, gen) {
  // Sample up to 10 midpoints along the route; color each stretch by
  // measured speed vs free-flow. No key or no data leaves the navy line.
  const pts = route.latlngs;
  if (pts.length < 4) return;
  const segs = Math.min(10, Math.max(4, Math.floor(pts.length / 30)));
  const bounds = [];
  for (let i = 0; i < segs; i++) {
    bounds.push(Math.floor(pts.length * i / segs));
  }
  bounds.push(pts.length - 1);
  const mids = [];
  for (let i = 0; i < segs; i++) {
    const m = pts[Math.floor((bounds[i] + bounds[i + 1]) / 2)];
    mids.push(m[0].toFixed(4) + ',' + m[1].toFixed(4));
  }
  try {
    const res = await fetch('/api/flow?pts=' + mids.join('|'));
    if (!res.ok) return;
    const data = await res.json();
    const flow = data.flow || [];
    if (!flow.some(f => f)) return;
    if (gen !== routeGen) return;  // route was replaced mid-fetch
    if (plannedRoute) plannedRoute.flow = { flow, bounds };
    showTrafficEta(route, pts, bounds, flow);
    paintStripFlow();
    layerRoute.removeLayer(baseLine);
    for (let i = 0; i < segs; i++) {
      const seg = pts.slice(bounds[i], bounds[i + 1] + 1);
      const f = flow[i];
      L.polyline(seg, {
        color: flowColor(f ? f.ratio : null), weight: 5, opacity: 0.9,
      }).bindPopup(f
        ? '<div class="pop"><div class="k"><i style="--dot:' +
          flowColor(f.ratio) + '"></i>TRAFFIC</div><div class="d">' +
          Math.round(f.current) + ' mph now vs ' + Math.round(f.freeflow) +
          ' mph free-flow</div></div>'
        : 'No speed data here', { maxWidth: 280 }).addTo(layerRoute);
    }
    if (reshapeGrab) reshapeGrab.bringToFront();
  } catch (e) { /* keep the navy line */ }
}

// The router's time is free-flow (no live speeds on the current plan),
// so the ETA is re-weighted with the measured speeds along the route:
// each sampled stretch takes its free-flow share of the trip time
// divided by measured-over-free-flow speed. Only slower counts; a
// stretch flowing above free flow does not shorten the trip.
function showTrafficEta(route, pts, bounds, flow) {
  const box = document.getElementById('routeeta');
  if (!box) return;
  const segLen = (seg) => {
    let m = 0;
    for (let k = 1; k < seg.length; k++) m += map.distance(seg[k - 1], seg[k]);
    return m;
  };
  let total = 0, weighted = 0, sampled = 0;
  for (let i = 0; i < bounds.length - 1; i++) {
    const len = segLen(pts.slice(bounds[i], bounds[i + 1] + 1));
    const f = flow[i];
    total += len;
    if (f && f.ratio) sampled += len;
    weighted += (f && f.ratio && f.ratio < 1) ? len / Math.max(0.25, f.ratio) : len;
  }
  if (!total || sampled / total < 0.5) { box.hidden = true; return; }
  const free = Math.round(route.duration / 60);
  const adjusted = Math.round(route.duration * (weighted / total) / 60);
  if (plannedRoute && plannedRoute.route === route) {
    plannedRoute.trafficMins = Math.max(free, adjusted);
    updateRouteHead();
    noteTrip();
  }
  if (adjusted - free < 2) {
    box.innerHTML = 'Traffic is flowing along this route right now: <b>about ' +
      free + ' min</b>.';
  } else {
    box.innerHTML = 'With current speeds along it: <b>about ' + adjusted +
      ' min</b>, against ' + free + ' min free-flow.';
  }
  box.hidden = false;
}

function wireReshape(route) {
  // A wide, invisible line over the route is the drag handle: pull it
  // anywhere and the trip re-routes through that spot. Via points stay
  // as draggable dots; clicking one removes it.
  const grab = L.polyline(route.latlngs, { color: '#000', weight: 22,
    opacity: 0.001, interactive: true }).addTo(layerRoute);
  reshapeGrab = grab;
  let ghost = null;
  grab.on('mousedown', (e) => {
    if (viaPoints.length >= 5) return;
    L.DomEvent.stop(e.originalEvent);
    map.dragging.disable();
    ghost = L.circleMarker(e.latlng, { radius: 7, color: '#fff',
      weight: 2, fillColor: '#0b1f33', fillOpacity: 1 }).addTo(layerRoute);
    const move = (ev) => ghost.setLatLng(ev.latlng);
    const finish = async (commit) => {
      map.off('mousemove', move); map.off('mouseup', up);
      document.removeEventListener('mouseup', docUp, true);
      map.dragging.enable();
      suppressPinOnce = true;
      setTimeout(() => { suppressPinOnce = false; }, 400);
      if (!ghost) return;
      const ll = ghost.getLatLng();
      layerRoute.removeLayer(ghost); ghost = null;
      if (commit) {
        viaPoints.push([ll.lat, ll.lng]);
        await replanVias();
      }
    };
    const up = () => finish(true);
    // Mouse released outside the map: cancel instead of stranding the
    // ghost dot with dragging disabled.
    const docUp = (ev) => {
      if (!document.getElementById('map').contains(ev.target)) finish(false);
    };
    map.on('mousemove', move);
    map.on('mouseup', up);
    document.addEventListener('mouseup', docUp, true);
  });
  for (const [i, v] of viaPoints.entries()) {
    const mk = L.marker(v, { draggable: true, zIndexOffset: 500,
      icon: L.divIcon({ className: 'viadot', iconSize: [16, 16] }) })
      .addTo(layerRoute);
    mk.bindTooltip('Drag to move \u00b7 click to remove');
    mk.on('dragend', async () => {
      const ll = mk.getLatLng();
      viaPoints[i] = [ll.lat, ll.lng];
      await replanVias();
    });
    mk.on('click', async () => {
      viaPoints.splice(i, 1);
      await replanVias();
    });
  }
}

let routeGen = 0;
let reshapeGrab = null;
function showRoute(route, others, a, b) {
  routeGen += 1;
  mobileReveal(document.getElementById('routealts'));
  plannedRoute = { route, a, b,
    fromName: fromF.input.dataset.name, toName: toF.input.dataset.name };
  plannedRoute.fromC = { name: plannedRoute.fromName, lat: a[0], lon: a[1] };
  plannedRoute.toC = { name: plannedRoute.toName, lat: b[0], lon: b[1] };
  const eta = document.getElementById('routeeta');
  if (eta) eta.hidden = true;
  layerRoute.clearLayers();
  for (const alt of others) {
    L.polyline(alt.latlngs, { color: '#7d93ab', weight: 3.5, opacity: 0.65,
      dashArray: '7 7' }).addTo(layerRoute);
  }
  const baseLine = L.polyline(route.latlngs,
    { color: '#0b1f33', weight: 4.5, opacity: 0.85 }).addTo(layerRoute);
  colorRouteByTraffic(route, baseLine, routeGen);
  wireReshape(route);
  [[a, 'A', plannedRoute.fromName], [b, 'B', plannedRoute.toName]].forEach(([pnt, letter, name]) => {
    const end = L.marker(pnt, { icon: L.divIcon({ className: 'route-end', html: letter, iconSize: [22, 22] }),
      zIndexOffset: 400, draggable: true }).bindPopup(esc(name)).addTo(layerRoute);
    end.bindTooltip('Drag to move the ' + (letter === 'A' ? 'start' : 'destination'));
    end.on('dragend', async () => {
      const ll = end.getLatLng();
      const field = letter === 'A' ? fromF : toF;
      const pinName = 'Pin ' + ll.lat.toFixed(3) + ' / ' + ll.lng.toFixed(3);
      field.input.value = pinName;
      field.input.dataset.lat = ll.lat;
      field.input.dataset.lon = ll.lng;
      field.input.dataset.name = pinName;
      const val = document.getElementById(letter === 'A' ? 'fromval' : 'toval');
      val.className = 'val ok'; val.textContent = '\u2713 ' + pinName;
      if (letter === 'A') lastEnds.a = [ll.lat, ll.lng];
      else lastEnds.b = [ll.lat, ll.lng];
      await replanVias();
    });
  });
  map.fitBounds(L.latLngBounds(route.latlngs), mapPad());
  setPlanned(true);
  updateRouteHead();
  noteTrip();
  const min = route.duration / 60;
  document.getElementById('routesum').textContent =
    plannedRoute.fromName.split(',')[0] + ' → ' + plannedRoute.toName.split(',')[0] +
    ', ' + csUnits.fmt(route.distance / 1000, 0) + ', ~' + Math.round(min) + ' min' +
    (route.via ? ', via ' + route.via.split(',')[0] : '');
  const ol = document.getElementById('steps');
  ol.innerHTML = '';
  document.getElementById('stepsdrop').open = false;
  document.getElementById('stepssummary').textContent =
    'Turn-by-turn directions (' + route.steps.length + ' steps)';
  route.steps.forEach(s => {
    const li = document.createElement('li');
    li.textContent = s.text + ' ';
    if (s.miles >= 0.05) {
      const sm = document.createElement('small');
      sm.textContent = '(' + (s.miles >= 9.5 ? Math.round(s.miles) : s.miles.toFixed(1)) +
        ' ' + csUnits.label() + ')';
      li.append(sm);
    }
    ol.append(li);
  });
  renderRouteConditions(route.latlngs);
  buildRouteAsks();
  document.getElementById('printwrap').style.display = 'block';
  beacon('example_click');
}

function nearRoute(m, latlngs, km) {
  const step = Math.max(1, Math.floor(latlngs.length / 60));
  for (let i = 0; i < latlngs.length; i += step) {
    const dlat = (m.lat - latlngs[i][0]) * 111.32;
    const dlon = (m.lon - latlngs[i][1]) * 111.32 *
      Math.cos(latlngs[i][0] * Math.PI / 180);
    if (dlat * dlat + dlon * dlon < km * km) return true;
  }
  return false;
}
let condHighlight = null;
let lastRouteLL = null;

function departEpoch() {
  if (document.getElementById('departmode').value !== 'later') return null;
  const v = document.getElementById('departat').value;
  if (!v) return null;
  const t = new Date(v).getTime();
  return Number.isFinite(t) && t > Date.now() ? Math.round(t / 1000) : null;
}

// What a condition means for a FUTURE departure, from its scheduled
// window. Deterministic: closure windows come straight from Caltrans;
// live incidents get an honest "probably gone by then" based on their
// short typical lifetime.
function departNote(m, g, dep) {
  const fmt = (ep) => clockTxt(ep) || '';
  if (g && g.startsWith('clo_')) {
    if (m.until && m.until < dep) {
      return ['gone', 'Scheduled to be picked up by ' + fmt(m.until) +
        ', before you leave'];
    }
    if (m.since && m.since > dep) {
      return ['active', 'Starts later: scheduled from ' + fmt(m.since)];
    }
    return ['active', m.until
      ? 'Expected still in place when you leave (until ' + fmt(m.until) + ')'
      : 'Expected still in place when you leave (no scheduled end)'];
  }
  if (g && g.startsWith('inc_')) {
    return ['gone', 'Live now; most CHP incidents clear within the hour'];
  }
  if (g === 'chain') {
    return ['active', 'Chain status changes with weather; check before leaving'];
  }
  if (g === 'fire_pt') return ['active', 'Ongoing fire; check again before leaving'];
  return [null, null];
}

function renderRouteConditions(latlngs) {
  // The list is about to rebuild: a ring belonging to a row that is
  // being destroyed would never get its mouseleave.
  if (condHighlight) { map.removeLayer(condHighlight); condHighlight = null; }
  lastRouteLL = latlngs;
  const box = document.getElementById('routecond');
  box.innerHTML = '<h4>Conditions on this route <span class="asof">as of ' +
    esc(fmtNowDay()) + '</span></h4>';
  const dep = departEpoch();
  if (dep) {
    const note = document.createElement('div');
    note.className = 'departnote';
    note.textContent = 'Planning for a ' + new Date(dep * 1000).toLocaleString([],
      { weekday: 'long', hour: 'numeric', minute: '2-digit' }) +
      ' departure: each item below says how its schedule lines up.';
    box.append(note);
  }
  let shown = 0;
  const condGroups = ['clo_full', 'clo_lane', 'clo_oneway', 'clo_ramp',
    'inc_collision', 'inc_fire', 'inc_hazard', 'inc_other',
    'chain', 'fire_pt', 'sign'];
  // Read the marker data, not the Leaflet layer groups: under the WebGL
  // renderer those groups stay empty and this list said "nothing
  // notable" on every modern browser. Listed in driving order, by the
  // mile each one sits at, start to finish.
  const along = routeMiles(latlngs);
  const hits = [];
  for (const g of condGroups) {
    for (const it of (items[g] || [])) {
      const m = it.m;
      if (!along.box.contains([m.lat, m.lon])) continue;
      // 0.35 km: on the roadway itself (plus GPS slop), not "nearby".
      if (!nearRoute(m, latlngs, 0.35)) continue;
      hits.push({ m, g, km: along.at(m) });
    }
  }
  hits.sort((x, y) => x.km - y.km);
  for (const { m, g, km } of hits.slice(0, 25)) {
    const row = document.createElement('div');
    row.className = 'condrow';
    const dot = document.createElement('i');
    dot.style.background = GROUP_DOT[g];
    const txt = document.createElement('span');
    const popEl = document.createElement('div');
    popEl.innerHTML = popupFor(m, g);
    const head = popEl.querySelector('h4, .t');
    const sub = popEl.querySelector('.sub, .d');
    txt.textContent = (head ? head.textContent : POP_LABEL[g]) +
      (sub && sub.textContent ? ' - ' + sub.textContent : '');
    const mi = document.createElement('b');
    mi.className = 'condmi';
    mi.textContent = csUnits.fmt(km, km < 10 ? 1 : 0);
    row.append(dot, txt, mi);
    if (dep) {
      const [cls, noteTxt] = departNote(m, g, dep);
      if (noteTxt) {
        const when = document.createElement('span');
        when.className = 'when' + (cls ? ' ' + cls : '');
        when.textContent = noteTxt;
        txt.append(when);
      }
    }
    const at = [m.lat, m.lon];
    row.addEventListener('mouseenter', () => {
      if (condHighlight) map.removeLayer(condHighlight);
      condHighlight = L.circleMarker(at, {
        radius: 15, color: '#0b1f33', weight: 3, fill: false,
      }).addTo(map);
    });
    row.addEventListener('mouseleave', () => {
      if (condHighlight) { map.removeLayer(condHighlight); condHighlight = null; }
    });
    row.addEventListener('click', () => {
      if (condHighlight) { map.removeLayer(condHighlight); condHighlight = null; }
      map.flyTo(at, Math.max(map.getZoom(), 12), { duration: 0.7 });
      setTimeout(() => {
        const p = L.popup({ maxWidth: 320 }).setLatLng(at).setContent(popupFor(m, g));
        p.__m = m; p.__g = g;
        p.openOn(map);
      }, 750);
    });
    box.append(row);
    shown++;
  }
  if (hits.length > shown) {
    const more = document.createElement('p');
    more.className = 'panenote';
    more.textContent = 'Showing the first ' + shown + ' of ' + hits.length +
      ' along the route. The route strip on the map has every one.';
    box.append(more);
  }
  buildRouteStrip(latlngs, along);
  if (!shown) {
    const row = document.createElement('div');
    row.textContent = 'Nothing notable reported along this route right now.';
    box.append(row);
  }
}

function buildRouteAsks() {
  clearPickMarks();  // the planned route now carries its own markers
  const wrap = document.getElementById('routeasks');
  wrap.innerHTML = '';
  // The assistant answers nationwide now (get_nearby_events serves the
  // multi-state feeds); route chips work for any US route.
  const wrapOuter = document.getElementById('routeasks-wrap');
  if (wrapOuter) wrapOuter.style.display = '';
  const a = plannedRoute.fromName.split(',')[0];
  const b = plannedRoute.toName.split(',')[0];
  const fromMe = a === 'My location';
  const to = fromMe ? 'to ' + b : 'from ' + a + ' to ' + b;
  const between = fromMe ? 'on my way to ' + b : 'between ' + a + ' and ' + b;

  // Templated, not AI: the pool flexes with the route (corridors it
  // uses, fires near it, mountain season, time of day) and the picks
  // shuffle so the chips feel alive without inventing anything.
  const r = plannedRoute.route;
  const miles = r.distance / 1609.344;
  const stepText = (r.steps || []).map((s) => s.text).join(' ');
  const corridors = [...new Set((stepText.match(
    /\b(?:I-\d{1,3}|US[- ]\d{1,3}|SR[- ]\d{1,3}|CA[- ]\d{1,3}|Highway \d{1,3})\b/gi) || [])
    .map((c) => c.replace(/\s+/, '-').replace(/^CA-/i, 'SR-').toUpperCase()))];
  const mountain = corridors.some((c) =>
    ['I-80', 'US-50', 'SR-88', 'SR-4', 'SR-108', 'SR-120', 'SR-89',
     'SR-267', 'SR-28', 'SR-2', 'SR-330', 'SR-18'].includes(c));
  const month = new Date().getMonth() + 1;   // chains: roughly Oct-Apr
  const chainSeason = month >= 10 || month <= 4;
  let fireNear = false;
  ambient.fire_pt.eachLayer((l) => {
    if (fireNear) return;
    const p = l.getLatLng ? l.getLatLng()
      : (l.getBounds ? l.getBounds().getCenter() : null);
    if (p && nearRoute({ lat: p.lat, lon: p.lng }, r.latlngs, 40)) fireNear = true;
  });
  const hour = new Date().getHours();
  const weekday = new Date().getDay() >= 1 && new Date().getDay() <= 5;
  const rush = weekday && ((hour >= 6 && hour <= 9) || (hour >= 15 && hour <= 19));

  const pool = [
    'Is there roadwork ' + between + '?',
    'What do the road signs say ' + between + '?',
    'Anything to worry about driving ' + to + ' today?',
    'What do the cameras show near ' + b + ' right now?',
    'Any big delays ' + between + ' right now?',
  ];
  for (const c of corridors.slice(0, 2)) pool.push('How is ' + c + ' right now?');
  if (mountain && chainSeason) {
    pool.push('Do I need chains ' + to + ' today?');
  }
  if (fireNear) pool.push('Are any fires affecting the drive ' + to + '?');
  if (rush) pool.push('How bad is rush hour ' + between + ' right now?');
  if (hour >= 20 || hour < 5) pool.push('Any overnight roadwork ' + between + '?');
  if (miles > 150) pool.push('Where are the trouble spots ' + between + '?');

  const questions = ['Will I hit traffic driving ' + to + ' right now?'];
  for (let i = pool.length - 1; i > 0; i--) {   // shuffle the rest
    const j = Math.floor(Math.random() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  questions.push(...pool.slice(0, 3));
  for (const q of questions) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = q;
    btn.addEventListener('click', () => {
      input.value = q;
      form.requestSubmit();
      beacon('tell_more');
      document.getElementById('result').scrollIntoView({ behavior: 'smooth' });
    });
    wrap.append(btn);
  }
}
document.getElementById('printbtn').addEventListener('click', () => {
  const drop = document.getElementById('stepsdrop');
  const wasOpen = drop.open;
  drop.open = true;
  window.print();
  drop.open = wasOpen;
});
document.getElementById('exportbtn').addEventListener('click', () => {
  if (!plannedRoute) return;
  const r = plannedRoute.route;
  const lines = [
    'CommuteScout - driving directions',
    plannedRoute.fromName + '  ->  ' + plannedRoute.toName,
    (r.distance / 1609.344).toFixed(0) + ' miles, about ' +
      Math.round(r.duration / 60) + ' minutes without delays',
    'Generated ' + new Date().toLocaleString() + ' - verify before you drive (511)',
    '',
    ...r.steps.map((s, i) => (i + 1) + '. ' + s.text +
      (s.miles >= 0.05 ? '  (' + s.miles.toFixed(1) + ' mi)' : '')),
    '',
    'Live conditions: https://commutescout.com',
  ];
  const blob = new Blob([lines.join('\r\n')], { type: 'text/plain' });
  const aEl = document.createElement('a');
  aEl.href = URL.createObjectURL(blob);
  aEl.download = 'directions.txt';
  aEl.click();
  URL.revokeObjectURL(aEl.href);
});


// ── Open one item's peek popup, after the map has landed on it ────
// The Live list, the Places list, the route strip and the palette all
// open items the same way the map does.
function openPeek(m, g, zoom) {
  const at = L.latLng(m.lat, m.lon);
  const z = Math.max(map.getZoom(), zoom || 11);
  const open = () => {
    const p = L.popup({ maxWidth: 320 }).setLatLng(at).setContent(popupFor(m, g));
    p.__m = m; p.__g = g;
    p.openOn(map);
  };
  if (map.getCenter().distanceTo(at) < 1 && map.getZoom() === z) open();
  else { map.once('moveend', open); map.setView(at, z); }
}
function kmBetween(a, b) {
  const dlat = (a.lat - b.lat) * 111.32;
  const dlon = (a.lon - b.lon) * 111.32 * Math.cos(a.lat * Math.PI / 180);
  return Math.sqrt(dlat * dlat + dlon * dlon);
}
// The live items the Live tool would list, inside a test, worst first.
function liveWhere(test) {
  const rows = [];
  for (const g of Object.keys(SEVERITY)) {
    if (!items[g] || !groupOn(g)) continue;
    for (const it of items[g]) if (test(it.m)) rows.push({ it, sev: SEVERITY[g] });
  }
  return rows;
}

// ── Your places: Home, Work, saved spots, recents, and what is live ──
// Kept in this browser (Places, cs.places.v1). Each place says how much
// is live within 5 km of it right now, counted from the map's own data.
const PLACE_KM = 5;
const placesPane = document.getElementById('pane-places');
const ptiles = document.getElementById('ptiles');
const pnote = document.getElementById('pnote');
const placesEditBtn = document.getElementById('placesedit');
let placesEditing = false;
let placeSlot = null;     // 'home' | 'work' | 'saved': the next search pick fills it
const PLACE_ICON = {
  home: '<path d="M4 11.5 12 5l8 6.5V20h-5v-5H9v5H4z"/>',
  work: '<rect x="4" y="8" width="16" height="11" rx="2"/><path d="M9 8V6a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 6v2M4 13h16"/>',
  saved: '<path d="M7 4h10a1 1 0 0 1 1 1v15l-6-4-6 4V5a1 1 0 0 1 1-1z"/>',
  recent: '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>',
  add: '<path d="M12 6v12M6 12h12"/>',
};
const svgIcon = (d) => '<svg viewBox="0 0 24 24" aria-hidden="true">' + d + '</svg>';
function liveNear(c) {
  return liveWhere((m) => kmBetween(m, c) <= PLACE_KM).length;
}
function armPlaceSlot(slot) {
  placeSlot = slot;
  const label = slot === 'home' ? 'Home' : slot === 'work' ? 'Work' : 'a saved place';
  pnote.hidden = false;
  pnote.innerHTML = '';
  const t = document.createElement('span');
  t.textContent = 'Search above the map, then pick a result to save it as ' + label + '.';
  const cancel = document.createElement('button');
  cancel.type = 'button'; cancel.className = 'txtbtn'; cancel.textContent = 'Cancel';
  cancel.addEventListener('click', () => { placeSlot = null; pnote.hidden = true; findF.input.placeholder = findPlaceholder; });
  pnote.append(t, cancel);
  findF.input.placeholder = slot === 'home' ? 'Search for your home address'
    : slot === 'work' ? 'Search for your work address' : 'Search for a place to save';
  if (isPhone()) setSheet('peek');
  findF.input.focus();
}
const findPlaceholder = findF.input.placeholder;
// Called by showFound: a pick made while a slot is armed is saved there.
function placesPicked(c) {
  if (!placeSlot) return;
  Places.set(placeSlot, c);
  placeSlot = null;
  pnote.hidden = true;
  findF.input.placeholder = findPlaceholder;
  renderPlaces();
}
// ── Trips: the drives planned in this browser, newest first ──────
// Kept here only (cs.trips.v1): the account's places list holds places,
// not trips. Recent lists them with their drive time, and a place's
// button shows the last drive time measured to it.
const Trips = {
  KEY: 'cs.trips.v1',
  load() {
    try { const t = JSON.parse(store.get(this.KEY) || '[]'); return Array.isArray(t) ? t : []; }
    catch (_) { return []; }
  },
  note(t) {
    if (!t || !t.a || !t.b || !isFinite(t.a.lat) || !isFinite(t.b.lat)) return;
    const list = this.load().filter((x) => !(Places.same(x.a, t.a) && Places.same(x.b, t.b)));
    list.unshift(t);
    store.set(this.KEY, JSON.stringify(list.slice(0, 12)));
  },
  toward(c) { return this.load().find((x) => Places.same(x.b, c)) || null; },
};
// Where you are, once you have asked (the locate button or "Use my
// location"); a place's button then says "Here" when you are at it.
let myPos = null;
function placeLabel(c) {
  if (!c) return 'Start';
  const p = Places.load();
  if (Places.same(c, p.home)) return 'Home';
  if (Places.same(c, p.work)) return 'Work';
  const s = p.saved.find((r) => Places.same(r, c));
  if (s) return s.name.split(', ')[0];
  const n = String(c.name || '');
  if (/^(my|your) location/i.test(n)) return 'Your location';
  return n.split(',')[0] || 'Dropped pin';
}
function tripTitle(t) { return placeLabel(t.a) + ' to ' + placeLabel(t.b); }
function whenTxt(at) {
  const d = new Date(at);
  const days = Math.round((new Date(new Date().toDateString()) - new Date(d.toDateString())) / 864e5);
  if (days <= 0) return 'Today, ' + d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  if (days === 1) return 'Yesterday';
  if (days < 7) return d.toLocaleDateString([], { weekday: 'short' });
  if (days < 14) return 'Last week';
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}
// Live data is in once a payload carried a time or any layer holds items.
const liveLoaded = () => !!snapPublished || Object.keys(items).some((g) => (items[g] || []).length);
const minsTxt = (m) => m >= 60 ? Math.floor(m / 60) + ' h ' + (m % 60) + ' min' : m + ' min';
// What a place's button says under its name: "Here" when you are at it,
// the drive time of your last trip there, or what is live around it.
function placeSub(c) {
  if (!c) return { text: 'Set', cls: 'set' };
  if (myPos && kmBetween(myPos, c) < 0.3) return { text: 'Here' };
  const t = Trips.toward(c);
  if (t && t.mins) {
    return { text: minsTxt(t.mins),
      title: 'Your last drive here (' + whenTxt(t.at).toLowerCase() + ')' };
  }
  if (!liveLoaded()) return { text: '' };
  const n = liveNear(c);
  return n ? { text: n + ' live near', cls: 'haslive',
    title: n + ' live within ' + csUnits.fmt(PLACE_KM, 0) }
    : { text: 'All clear', title: 'Nothing live within ' + csUnits.fmt(PLACE_KM, 0) };
}
function placeTile(kind, c, label) {
  const li = document.createElement('li');
  li.className = 'pfav ' + kind + (c ? '' : ' unset');
  const main = document.createElement('button');
  main.type = 'button';
  main.className = 'pbtn';
  const sub = placeSub(c);
  main.innerHTML = '<span class="pcirc">' + svgIcon(PLACE_ICON[kind]) + '</span>' +
    '<span class="plbl">' + esc(label) + '</span>' +
    '<small class="psub' + (sub.cls ? ' ' + sub.cls : '') + '">' + esc(sub.text) + '</small>';
  main.title = c ? 'Directions to ' + c.name + (sub.title ? '. ' + sub.title : '')
    : 'Set your ' + label.toLowerCase() + ' address';
  main.addEventListener('click', () => {
    if (placesEditing && c) return;
    if (c) navigateTo(Object.assign({}, c));
    else armPlaceSlot(kind);
  });
  li.append(main);
  if (c && placesEditing) {
    const rm = document.createElement('button');
    rm.type = 'button'; rm.className = 'prm';
    rm.setAttribute('aria-label', 'Remove ' + label);
    rm.title = 'Remove ' + label;
    rm.innerHTML = svgIcon('<path d="M7 7l10 10M17 7 7 17"/>');
    rm.addEventListener('click', () => { Places.remove(kind, c); renderPlaces(); });
    li.append(rm);
  }
  return li;
}
function renderPlaces() {
  if (!placesPane.classList.contains('on')) return;
  const p = Places.load();
  ptiles.replaceChildren(
    placeTile('home', p.home, 'Home'),
    placeTile('work', p.work, 'Work'),
    ...p.saved.map((c) => placeTile('saved', c, c.name.split(', ')[0])));
  if (p.saved.length < PLACES_CAP) {
    const li = document.createElement('li');
    li.className = 'pfav add';
    const add = document.createElement('button');
    add.type = 'button'; add.className = 'pbtn padd';
    add.innerHTML = '<span class="pcirc">' + svgIcon(PLACE_ICON.add) + '</span><span class="plbl">Add</span>' +
      '<small class="psub"></small>';
    add.title = 'Save a place';
    add.addEventListener('click', () => armPlaceSlot('saved'));
    li.append(add);
    ptiles.append(li);
  }
  placesEditBtn.hidden = !(p.home || p.work || p.saved.length);
  document.getElementById('psync').textContent = PlaceSync.signedIn
    ? 'Synced with your account.'
    : 'Saved in this browser. Sign in to sync with the app and your AI assistant.';
  document.getElementById('psignin').hidden = PlaceSync.signedIn;
  // Recent: the trips planned here (with their drive time), then places
  // searched for, newest first; a destination already in a trip is not
  // listed twice.
  const trips = Trips.load();
  const rows = trips.map((t) => ({ at: t.at || 0, title: tripTitle(t),
    meta: [whenTxt(t.at), t.mins ? minsTxt(t.mins) : null].filter(Boolean).join(' · '),
    label: 'Plan ' + tripTitle(t) + ' again',
    go: () => replanTrip(t) }));
  for (const c of p.recents) {
    if (Places.same(c, p.home) || Places.same(c, p.work)) continue;
    if (trips.some((t) => Places.same(t.b, c))) continue;
    const parts = c.name.split(', ');
    rows.push({ at: c.at || 0, title: parts[0], meta: c.at ? whenTxt(c.at) : (parts.slice(1).join(', ') || ''),
      label: 'Directions to ' + c.name, go: () => navigateTo(Object.assign({}, c)) });
  }
  rows.sort((x, y) => y.at - x.at);
  const wrap = document.getElementById('precentwrap');
  const list = document.getElementById('precent');
  wrap.hidden = !rows.length;
  list.replaceChildren(...rows.slice(0, 3).map((r) => {
    const row = document.createElement('button');
    row.type = 'button'; row.className = 'prow';
    row.innerHTML = '<span class="pclock">' + svgIcon(PLACE_ICON.recent) + '</span><span><b>' +
      esc(r.title) + '</b><small>' + esc(r.meta) + '</small></span>';
    row.title = r.label;
    row.addEventListener('click', r.go);
    return row;
  }));
  refreshPlacesLive();
}
// A recent trip, planned again from the same two ends.
function replanTrip(t) {
  fromF.pick(Object.assign({}, t.a));
  toF.pick(Object.assign({}, t.b));
  setTool('route', { toggle: false, reveal: true });
  planbtn.click();
}
placesEditBtn.addEventListener('click', () => {
  placesEditing = !placesEditing;
  placesEditBtn.textContent = placesEditing ? 'Done' : 'Edit';
  placesEditBtn.setAttribute('aria-pressed', placesEditing ? 'true' : 'false');
  renderPlaces();
});
document.getElementById('pliveall').addEventListener('click', () => {
  setTool('alerts', { toggle: false, reveal: true });
  scheduleAlerts();
});
// Live near you: what the Live tool would list for the map in view,
// worst first, the first three of them; the count is everything in view.
const PLACES_LIVE_ROWS = 3;
function refreshPlacesLive() {
  if (!placesPane.classList.contains('on')) return;
  const b = map.getBounds();
  const c = map.getCenter();
  const rows = liveWhere((m) => b.contains([m.lat, m.lon]));
  const count = document.getElementById('pchips');
  const all = document.getElementById('pliveall');
  count.textContent = liveLoaded() ? rows.length.toLocaleString() + ' in view' : '';
  all.hidden = !rows.length;
  all.innerHTML = 'See all ' + rows.length.toLocaleString() + ', worst first ' +
    svgIcon('<path d="m9 6 6 6-6 6"/>');
  const list = document.getElementById('plive');
  if (!rows.length) {
    list.innerHTML = '<p class="panenote">' + (liveLoaded()
      ? 'Nothing live in view for the layers you have on. Zoom out or switch on more layers.'
      : 'Loading what is on the map&hellip;') + '</p>';
    return;
  }
  rows.forEach((r) => { r.d = map.distance(c, [r.it.m.lat, r.it.m.lon]); });
  rows.sort((x, y) => x.sev - y.sev || x.d - y.d);
  list.replaceChildren(...rows.slice(0, PLACES_LIVE_ROWS).map((r) => {
    const row = alertRow(r.it.m, r.it.g);
    const btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'alertrow';
    btn.innerHTML = kindIcon(r.it.g) + '<span><b>' +
      esc(String(row.title).slice(0, 110)) + '</b><small>' + esc(row.sub) + '</small></span>';
    btn.addEventListener('click', () => openPeek(r.it.m, r.it.g));
    return btn;
  }));
}
// The places list follows the Live list's refresh (scheduleAlerts runs
// it on every move and data load); the tiles' counts every 30 seconds.
setInterval(renderPlaces, 30000);
[1500, 4000, 9000].forEach((ms) => setTimeout(renderPlaces, ms));
document.querySelectorAll('#filters input[data-group]').forEach((box) => {
  box.addEventListener('change', () => setTimeout(renderPlaces, 60));
});
document.addEventListener('cs-tool', (e) => { if (e.detail === 'places') renderPlaces(); });
document.addEventListener('cs-places', () => renderPlaces());
document.getElementById('psignin').addEventListener('click', () => {
  setTool('watch', { toggle: false, reveal: true });
});
renderPlaces();

// ── Route strip: the planned trip, start to finish, item by item ──
// Board #11, in the panel: one row per item on the route at its mile,
// the start and the destination at either end, and a line between rows
// coloured by the measured traffic on that stretch. Click a row, or
// step with the arrows, and the map flies to it with its popup open.
const rstrip = document.getElementById('rstrip');
const rstrack = document.getElementById('rstrack');
const STRIP_EXTRA = ['camera', 'rwis', 'plugin'];  // shown when their layer is on
let stripItems = [];   // rows: {m, g, km} for an item, {end: 'a' | 'b', km} for the ends
let stripSel = -1;
function routeMiles(latlngs) {
  const cum = [0];
  for (let i = 1; i < latlngs.length; i++) {
    cum.push(cum[i - 1] + kmBetween({ lat: latlngs[i - 1][0], lon: latlngs[i - 1][1] },
      { lat: latlngs[i][0], lon: latlngs[i][1] }));
  }
  const box = L.latLngBounds(latlngs);
  const pad = 0.01;   // about a kilometre, more than the 0.35 km match
  const padded = L.latLngBounds([box.getSouth() - pad, box.getWest() - pad],
    [box.getNorth() + pad, box.getEast() + pad]);
  return {
    total: cum[cum.length - 1] || 0,
    box: padded,
    cum,
    // The km along the route of the vertex nearest the item.
    at(m) {
      let best = 0, bd = Infinity;
      for (let i = 0; i < latlngs.length; i++) {
        const dlat = m.lat - latlngs[i][0], dlon = (m.lon - latlngs[i][1]) * Math.cos(m.lat * Math.PI / 180);
        const d = dlat * dlat + dlon * dlon;
        if (d < bd) { bd = d; best = i; }
      }
      return cum[best];
    },
  };
}
// "MESSAGE SIGN" -> "Message sign": the popup labels are set in caps by CSS elsewhere.
function kindName(g) {
  const t = String(POP_LABEL[g] || g).toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
}
function hideRouteStrip() {
  stripItems = []; stripSel = -1;
  rstrip.hidden = true;
  rstrack.replaceChildren();
}
// The measured speed over free flow on the stretch around a mile, from
// the samples colorRouteByTraffic took (none: no class, a neutral line).
function flowClass(ratio) {
  return ratio == null ? '' : ratio >= 0.8 ? 'moving' : ratio >= 0.55 ? 'slow' : 'jam';
}
function flowAtKm(km) {
  const f = plannedRoute && plannedRoute.flow;
  const along = plannedRoute && plannedRoute.along;
  if (!f || !along) return null;
  for (let i = 0; i < f.bounds.length - 1; i++) {
    if (km <= along.cum[f.bounds[i + 1]]) return f.flow[i] ? f.flow[i].ratio : null;
  }
  return null;
}
function paintStripFlow() {
  let any = false;
  rstrack.querySelectorAll('.rsrow').forEach((row, i) => {
    const seg = row.querySelector('.rsseg');
    if (!seg || !stripItems[i + 1]) return;
    const cls = flowClass(flowAtKm((stripItems[i].km + stripItems[i + 1].km) / 2));
    seg.className = 'rsseg' + (cls ? ' ' + cls : '');
    if (cls) any = true;
  });
  document.getElementById('rslegend').hidden = !any;
}
const clockTxtMs = (ms) => new Date(ms).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
function stripMile(km) {
  const v = csUnits.fromKm(km);
  return csUnits.label() + ' ' + (v >= 100 ? Math.round(v) : v.toFixed(1));
}
function buildRouteStrip(latlngs, along) {
  if (!plannedRoute) return;
  plannedRoute.along = along;
  const groups = ['clo_full', 'clo_lane', 'clo_oneway', 'clo_ramp', 'inc_collision', 'inc_fire',
    'inc_hazard', 'inc_other', 'chain', 'fire_pt', 'sign'].concat(STRIP_EXTRA.filter(groupOn));
  const hits = [];
  for (const g of groups) {
    for (const it of (items[g] || [])) {
      const m = it.m;
      if (!along.box.contains([m.lat, m.lon]) || !nearRoute(m, latlngs, 0.35)) continue;
      hits.push({ m, g, km: along.at(m) });
    }
  }
  hits.sort((x, y) => x.km - y.km);
  const total = along.total || 0;
  const r = plannedRoute.route;
  const dep = departEpoch();
  const leave = dep ? dep * 1000 : Date.now();
  const mins = plannedRoute.trafficMins || Math.round(r.duration / 60);
  stripItems = [{ end: 'a', km: 0 }, ...hits, { end: 'b', km: total }];
  stripSel = -1;
  const rows = stripItems.map((h, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.id = 'rsrow' + i;
    b.className = 'rsrow' + (h.end ? ' end' : '');
    b.tabIndex = -1;
    b.setAttribute('role', 'option');
    b.setAttribute('aria-selected', 'false');
    let title, meta, mark;
    if (h.end) {
      title = placeLabel(h.end === 'a' ? plannedRoute.fromC : plannedRoute.toC);
      meta = h.end === 'a' ? 'Leave ' + clockTxtMs(leave)
        : 'Arrive about ' + clockTxtMs(leave + mins * 60000);
      mark = '<span class="rsend ' + h.end + '" aria-hidden="true"></span>';
    } else {
      const row = alertRow(h.m, h.g);
      title = String(row.title).slice(0, 120);
      const [, when] = dep ? departNote(h.m, h.g, dep) : [null, null];
      meta = [row.sub, when].filter(Boolean).join(' · ');
      mark = kindIcon(h.g, 'sm');
      b.setAttribute('aria-label', kindName(h.g) + ': ' + title + ', at ' + csUnits.fmt(h.km, 1));
    }
    b.innerHTML = '<span class="rsmi">' + stripMile(h.km) + '</span>' +
      '<span class="rsmark">' + (i < stripItems.length - 1 ? '<i class="rsseg"></i>' : '') + mark + '</span>' +
      '<span class="rstxt"><b>' + esc(title) + '</b><small>' + esc(meta) + '</small></span>';
    b.addEventListener('click', () => selectStrip(i, true));
    return b;
  });
  rstrack.replaceChildren(...rows);
  rstrack.removeAttribute('aria-activedescendant');
  ['rsprev', 'rsnext'].forEach((id) => { document.getElementById(id).disabled = !hits.length; });
  document.getElementById('rspos').textContent = hits.length
    ? hits.length + (hits.length === 1 ? ' item' : ' items') + ' on the way' : 'Nothing reported on the way';
  rstrip.hidden = false;
  paintStripFlow();
}
function selectStrip(i, fly) {
  if (!stripItems.length) return;
  stripSel = Math.max(0, Math.min(stripItems.length - 1, i));
  const h = stripItems[stripSel];
  rstrack.querySelectorAll('.rsrow').forEach((b, j) => {
    b.classList.toggle('on', j === stripSel);
    b.setAttribute('aria-selected', j === stripSel ? 'true' : 'false');
  });
  rstrack.setAttribute('aria-activedescendant', 'rsrow' + stripSel);
  const rowEl = document.getElementById('rsrow' + stripSel);
  if (rowEl) rowEl.scrollIntoView({ block: 'nearest' });
  const n = stripItems.length - 2;
  document.getElementById('rspos').textContent = h.end ? (n + (n === 1 ? ' item' : ' items') + ' on the way')
    : stripSel + ' of ' + n;
  if (!fly) return;
  if (h.end) {
    const at = h.end === 'a' ? plannedRoute.a : plannedRoute.b;
    map.setView(at, Math.max(map.getZoom(), 13));
  } else openPeek(h.m, h.g, 12);
}
// The arrows step through the items, skipping the two ends.
document.getElementById('rsprev').addEventListener('click', () => {
  const n = stripItems.length - 2;
  if (n > 0) selectStrip(stripSel <= 1 ? n : stripSel - 1, true);
});
document.getElementById('rsnext').addEventListener('click', () => {
  const n = stripItems.length - 2;
  if (n > 0) selectStrip(stripSel < 1 || stripSel >= n ? 1 : stripSel + 1, true);
});
rstrack.addEventListener('keydown', (e) => {
  const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
  if (step) { e.preventDefault(); selectStrip(stripSel < 0 ? (step > 0 ? 0 : stripItems.length - 1) : stripSel + step, true); }
  else if (e.key === 'Home') { e.preventDefault(); selectStrip(0, true); }
  else if (e.key === 'End') { e.preventDefault(); selectStrip(stripItems.length - 1, true); }
  else if (e.key === 'Enter' && stripSel >= 0 && !stripItems[stripSel].end) {
    e.preventDefault(); openInspector(stripItems[stripSel].m, stripItems[stripSel].g);
  }
});

// ── Map controls, board #3: Layers top right, locate and zoom bottom
// right, and the live pill at the foot of the map beside the panel ──
if (map.zoomControl) map.zoomControl.remove();
document.getElementById('zoomin').addEventListener('click', () => map.zoomIn());
document.getElementById('zoomout').addEventListener('click', () => map.zoomOut());
function syncZoomBtns() {
  document.getElementById('zoomin').disabled = map.getZoom() >= map.getMaxZoom();
  document.getElementById('zoomout').disabled = map.getZoom() <= map.getMinZoom();
}
map.on('zoomend', syncZoomBtns);
syncZoomBtns();
let myDot = null;
const locBtn = document.getElementById('locbtn');
locBtn.addEventListener('click', () => {
  if (!navigator.geolocation) { locBtn.title = 'Location is not available in this browser'; return; }
  locBtn.classList.add('busy');
  locBtn.setAttribute('aria-busy', 'true');
  navigator.geolocation.getCurrentPosition((pos) => {
    locBtn.classList.remove('busy'); locBtn.removeAttribute('aria-busy');
    myPos = { lat: pos.coords.latitude, lon: pos.coords.longitude };
    const ll = [myPos.lat, myPos.lon];
    if (myDot) myDot.setLatLng(ll);
    else {
      myDot = L.marker(ll, { interactive: false, keyboard: false, zIndexOffset: 600,
        icon: L.divIcon({ className: 'mydot', iconSize: [18, 18] }) }).addTo(map);
    }
    locBtn.classList.add('on');
    map.setView(ll, Math.max(map.getZoom(), 13));
    renderPlaces();
  }, () => {
    locBtn.classList.remove('busy'); locBtn.removeAttribute('aria-busy');
    locBtn.title = 'Location was blocked. Allow it for this site to use this button.';
  }, { enableHighAccuracy: false, timeout: 8000, maximumAge: 120000 });
});
// "Live · updated 12 s ago": the age of the newest data on the map.
function paintLivePill() {
  const el = document.getElementById('liveage');
  if (!snapPublished) { el.textContent = 'Live'; return; }
  const s = Math.max(0, Math.round((Date.now() - snapPublished) / 1000));
  el.textContent = 'Live · updated ' + (s < 60 ? s + ' s' : s < 3600 ? Math.round(s / 60) + ' min'
    : Math.round(s / 3600) + ' h') + ' ago';
  document.getElementById('livepill').classList.toggle('stale', s > 15 * 60);
}
paintLivePill();
setInterval(paintLivePill, 5000);

// ── Layers: a popover from the map's Layers button ───────────────
// Board #3 keeps layers off the rail; the button carries how many are
// switched off. The list itself is the Layers section of the panel,
// lifted out over the map while it is open.
const layersBtn = document.getElementById('layersbtn');
const layersPane = document.getElementById('pane-layers');
function paintLayersBadge() {
  const off = document.querySelectorAll('#filters input[data-group]:not(:checked)').length;
  const b = document.getElementById('layersoff');
  b.textContent = off + ' off';
  b.hidden = !off;
  layersBtn.setAttribute('aria-label', 'Layers' + (off ? ', ' + off + ' switched off' : ''));
}
function setLayersOpen(open, refocus) {
  layersPane.classList.toggle('pop', !!open);
  shellEl.classList.toggle('lyropen', !!open);
  layersBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
  if (open) {
    if (isPhone() && sheetState !== 'peek') setSheet('peek');
    document.getElementById('lyrclose').focus();
  } else if (refocus) layersBtn.focus();
}
function openLayers() { setLayersOpen(true); }
layersBtn.addEventListener('click', () => setLayersOpen(!layersPane.classList.contains('pop'), true));
document.getElementById('lyrclose').addEventListener('click', () => setLayersOpen(false, true));
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && layersPane.classList.contains('pop')) { e.stopPropagation(); setLayersOpen(false, true); }
}, true);
document.addEventListener('pointerdown', (e) => {
  if (layersPane.classList.contains('pop') && !layersPane.contains(e.target) && !layersBtn.contains(e.target)) {
    setLayersOpen(false);
  }
});
document.getElementById('filters').addEventListener('change', paintLayersBadge);
paintLayersBadge();

// ── The rail: slim by default, expands to labels and the rest ─────
const RAIL_WIDE_KEY = 'cs-rail-wide';
const railX = document.getElementById('railexpand');
function setRailWide(on) {
  shellEl.classList.toggle('railwide', on);
  railX.setAttribute('aria-expanded', on ? 'true' : 'false');
  railX.querySelector('span').textContent = on ? (isPhone() ? 'Close' : 'Collapse') : 'More';
  railX.title = on ? 'Collapse the rail' : 'Show more tools and labels';
  if (!isPhone()) store.set(RAIL_WIDE_KEY, on ? '1' : '');
  setTimeout(() => map.invalidateSize(), 220);
}
railX.addEventListener('click', () => setRailWide(!shellEl.classList.contains('railwide')));
setRailWide(!isPhone() && store.get(RAIL_WIDE_KEY) === '1');
// On a phone the expanded rail is a menu over the tab bar: picking from
// it, or tapping elsewhere, closes it.
document.getElementById('railadv').addEventListener('click', (e) => {
  if (isPhone() && e.target.closest('.tool')) setRailWide(false);
});
document.addEventListener('pointerdown', (e) => {
  if (isPhone() && shellEl.classList.contains('railwide') && !railEl.contains(e.target)) setRailWide(false);
});
railEl.addEventListener('click', (e) => {
  const act = e.target.closest('[data-act]');
  if (!act || act.tagName !== 'BUTTON') return;
  runAction(act.dataset.act);
});
function runAction(name) {
  if (name === 'keys') {
    setTool('settings', { toggle: false, reveal: true });
    loadWatch().then(() => setTimeout(() => {
      const card = document.getElementById('keycard');
      const target = card && !card.hidden ? card : document.getElementById('acctnote');
      if (target) target.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }, 300));
  } else if (name === 'report') {
    startReport();
  } else if (name === 'theme') {
    setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  } else if (name === 'palette') {
    openPalette();
  }
}

// ── Theme: light or dark, the site's own setting (cs-theme) ───────
// basemap-early.js applied it before first paint. With no base map
// chosen, the map follows: Dark on a dark page, Positron on a light one.
const darkMq = window.matchMedia('(prefers-color-scheme: dark)');
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.getElementById('railtheme').textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
  let chosenBase = null;
  try { chosenBase = localStorage.getItem('cs-basemap'); } catch (_) { /* private mode */ }
  if (!chosenBase) {
    const radio = document.querySelector('#basemap input[value="' + (theme === 'dark' ? 'Dark' : 'Positron') + '"]');
    if (radio && !radio.checked) {
      radio.checked = true;
      radio.dispatchEvent(new Event('change', { bubbles: true }));
      try { localStorage.removeItem('cs-basemap'); } catch (_) { /* private mode */ }
    }
  }
}
function setTheme(choice) {
  try {
    if (choice === 'system') localStorage.removeItem('cs-theme');
    else localStorage.setItem('cs-theme', choice);
  } catch (_) { /* private mode */ }
  applyTheme(choice === 'system' ? (darkMq.matches ? 'dark' : 'light') : choice);
}
darkMq.addEventListener('change', () => {
  let saved = null;
  try { saved = localStorage.getItem('cs-theme'); } catch (_) { /* private mode */ }
  if (saved !== 'light' && saved !== 'dark') applyTheme(darkMq.matches ? 'dark' : 'light');
});
document.getElementById('railtheme').textContent =
  document.documentElement.dataset.theme === 'dark' ? 'Light mode' : 'Dark mode';

// ── Command palette (Cmd-K / Ctrl-K) ──────────────────────────────
// One box for every real action on the page: places, a place search,
// tools, layers, base maps, units and theme. Each command calls the
// same code its button does.
const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || '');
const cpal = document.getElementById('cpal');
const cpalQ = document.getElementById('cpalq');
const cpalList = document.getElementById('cpallist');
document.getElementById('cpalkey').textContent = IS_MAC ? '⌘K' : 'Ctrl K';
document.getElementById('cpalhint').addEventListener('click', () => openPalette());
let palCmds = [];
let palSel = 0;
let palOpener = null;
let palSearchSeq = 0;
let palPlaces = [];
function labelText(input) {
  const lab = input.closest('label');
  if (!lab) return input.value;
  return Array.from(lab.childNodes).filter((n) => n.nodeType === 3).map((n) => n.textContent).join(' ').trim();
}
function paletteCommands() {
  const cmds = [];
  const add = (group, label, run, hint, keys) => cmds.push({ group, label, run, hint: hint || '', keys: [keys, label, hint].filter(Boolean).join(' ') });
  const p = Places.load();
  if (p.home) add('Places', 'Directions to Home', () => navigateTo(Object.assign({}, p.home)), p.home.name.split(', ')[0], 'home');
  else add('Places', 'Set your Home address', () => { setTool('places', { toggle: false, reveal: true }); armPlaceSlot('home'); }, '', 'home');
  if (p.work) add('Places', 'Directions to Work', () => navigateTo(Object.assign({}, p.work)), p.work.name.split(', ')[0], 'work office');
  else add('Places', 'Set your Work address', () => { setTool('places', { toggle: false, reveal: true }); armPlaceSlot('work'); }, '', 'work office');
  p.saved.forEach((c) => add('Places', 'Directions to ' + c.name.split(', ')[0], () => navigateTo(Object.assign({}, c)), 'Saved', 'saved favorite'));
  p.recents.slice(0, 3).forEach((c) => add('Places', c.name.split(', ')[0], () => navigateTo(Object.assign({}, c)), 'Recent', 'recent'));
  palPlaces.forEach((c) => add('Search results', c.name.split(', ')[0], () => showFound(c), c.name.split(', ').slice(1).join(', '), 'search find'));
  add('Actions', 'Plan a route', () => { setTool('route', { toggle: false, reveal: true }); fromF.input.focus(); }, '', 'directions navigate trip');
  add('Actions', 'Your places', () => setTool('places', { toggle: false, reveal: true }), '', 'home saved');
  add('Actions', 'Live right now', () => { setTool('alerts', { toggle: false, reveal: true }); scheduleAlerts(); }, '', 'alerts incidents closures');
  add('Actions', 'Layers', () => openLayers(), '', 'filters show hide');
  add('Actions', 'Ask about your drive', () => { setTool('ask', { toggle: false, reveal: true }); document.getElementById('q').focus(); }, '', 'assistant question ai');
  add('Actions', 'Report something on the road', () => runAction('report'), '', 'report hazard');
  add('Actions', 'Watch areas', () => setTool('watch', { toggle: false, reveal: true }), '', 'alerts notify watch');
  add('Actions', 'Settings', () => setTool('settings', { toggle: false, reveal: true }), '', 'account preferences');
  add('Actions', 'API keys', () => runAction('keys'), 'Settings', 'developer key token');
  add('Actions', 'About the data', () => setTool('about', { toggle: false, reveal: true }), '', 'sources legal privacy');
  add('Actions', shellEl.classList.contains('railwide') ? 'Collapse the rail' : 'Expand the rail', () => setRailWide(!shellEl.classList.contains('railwide')), '', 'sidebar menu');
  if (plannedRoute) {
    add('Route', 'Show what is along the route', () => { setTool('route', { toggle: false, reveal: true }); rstrack.focus(); }, '', 'strip along');
    add('Route', 'Copy a share link', () => document.getElementById('sharebtn').click(), '', 'share link');
    add('Route', 'Export as GPX', () => document.getElementById('gpxbtn').click(), '', 'gpx download');
    add('Route', 'Export as KML', () => document.getElementById('kmlbtn').click(), '', 'kml download');
    add('Route', 'Clear the route', () => document.getElementById('clearroutebtn').click(), '', 'remove reset');
  }
  if (!inspectorEl.hidden) add('Actions', 'Close the details pane', closeInspector, '', 'inspector');
  document.querySelectorAll('#filters input[data-group]').forEach((box) => {
    add('Layers', labelText(box), () => { box.click(); }, box.checked ? 'On' : 'Off', 'layer toggle show hide');
  });
  const traffic = document.getElementById('trafficlayer');
  add('Layers', 'Live traffic overlay', () => traffic.click(), traffic.checked ? 'On' : 'Off', 'layer traffic flow');
  document.querySelectorAll('#basemap input[name="basemap"]').forEach((r) => {
    add('Map style', r.value + ' base map', () => { if (!r.checked) { r.checked = true; r.dispatchEvent(new Event('change', { bubbles: true })); } },
      r.checked ? 'Current' : '', 'basemap style');
  });
  document.querySelectorAll('#unitpick input[name="units"]').forEach((r) => {
    add('Units', r.value === 'mi' ? 'Distances in miles' : 'Distances in kilometers', () => csUnits.set(r.value),
      csUnits.get() === r.value ? 'Current' : '', 'units');
  });
  const theme = document.documentElement.dataset.theme;
  let savedTheme = null;
  try { savedTheme = localStorage.getItem('cs-theme'); } catch (_) { /* private mode */ }
  add('Theme', 'Light theme', () => setTheme('light'), savedTheme === 'light' ? 'Current' : '', 'appearance');
  add('Theme', 'Dark theme', () => setTheme('dark'), savedTheme === 'dark' ? 'Current' : '', 'appearance night');
  add('Theme', 'Match the system', () => setTheme('system'), !savedTheme ? 'Current, ' + theme : '', 'appearance auto');
  return cmds;
}
// Every word typed must start a word in the label or its keywords.
function palMatch(cmd, words) {
  if (!words.length) return true;
  const hay = cmd.keys.toLowerCase().split(/[^a-z0-9]+/);
  return words.every((w) => hay.some((h) => h.startsWith(w)));
}
function renderPalette() {
  const q = cpalQ.value.trim();
  const words = q.toLowerCase().split(/\s+/).filter(Boolean);
  const all = paletteCommands();
  palCmds = all.filter((c) => c.group === 'Search results' || palMatch(c, words));
  if (q.length >= 2) {
    const coord = parseCoords(q);
    if (coord && !palPlaces.length) palCmds.unshift({ group: 'Search results', label: coord.name, run: () => showFound(coord), hint: 'Coordinates', keys: '' });
    palCmds.push({ group: 'Ask', label: 'Ask: ' + q, hint: 'Assistant', keys: '', run: () => {
      setTool('ask', { toggle: false, reveal: true });
      const box = document.getElementById('q');
      box.value = q.slice(0, 300);
      document.getElementById('form').requestSubmit();
    } });
  }
  palSel = Math.min(palSel, Math.max(0, palCmds.length - 1));
  cpalList.replaceChildren();
  let group = null;
  palCmds.forEach((c, i) => {
    if (c.group !== group) {
      group = c.group;
      const h = document.createElement('div');
      h.className = 'cpalgrp'; h.setAttribute('role', 'presentation');
      h.textContent = group;
      cpalList.append(h);
    }
    const row = document.createElement('div');
    row.className = 'cpalrow' + (i === palSel ? ' on' : '');
    row.id = 'cpal-' + i;
    row.setAttribute('role', 'option');
    row.setAttribute('aria-selected', i === palSel ? 'true' : 'false');
    const t = document.createElement('span'); t.textContent = c.label;
    row.append(t);
    if (c.hint) { const h = document.createElement('small'); h.textContent = c.hint; row.append(h); }
    row.addEventListener('mousemove', () => { if (palSel !== i) { palSel = i; markPalette(); } });
    row.addEventListener('click', () => runPalette(i));
    cpalList.append(row);
  });
  if (!palCmds.length) {
    const none = document.createElement('p');
    none.className = 'cpalnone';
    none.textContent = 'No command matches. Type at least two letters to search places.';
    cpalList.append(none);
  }
  markPalette();
}
function markPalette() {
  cpalList.querySelectorAll('.cpalrow').forEach((r, i) => {
    r.classList.toggle('on', i === palSel);
    r.setAttribute('aria-selected', i === palSel ? 'true' : 'false');
  });
  const cur = document.getElementById('cpal-' + palSel);
  cpalQ.setAttribute('aria-activedescendant', cur ? cur.id : '');
  if (cur) cur.scrollIntoView({ block: 'nearest' });
}
function runPalette(i) {
  const c = palCmds[i];
  if (!c) return;
  closePalette(false);
  c.run();
}
let palTimer = null;
cpalQ.addEventListener('input', () => {
  palSel = 0;
  palPlaces = [];
  renderPalette();
  clearTimeout(palTimer);
  const q = cpalQ.value.trim();
  if (q.length < 2 || parseCoords(q)) return;
  palTimer = setTimeout(async () => {
    const mine = ++palSearchSeq;
    try {
      const c = map.getCenter();
      const res = await fetch('/api/suggest?q=' + encodeURIComponent(q) +
        '&lat=' + c.lat.toFixed(2) + '&lon=' + c.lng.toFixed(2));
      const data = await res.json();
      if (mine !== palSearchSeq || cpal.hidden) return;
      palPlaces = (data.suggestions || []).slice(0, 5);
      renderPalette();
    } catch (_) { /* offline: the other commands still work */ }
  }, 220);
});
cpalQ.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowDown') { e.preventDefault(); palSel = Math.min(palCmds.length - 1, palSel + 1); markPalette(); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); palSel = Math.max(0, palSel - 1); markPalette(); }
  else if (e.key === 'Enter') { e.preventDefault(); runPalette(palSel); }
});
cpal.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closePalette(true); }
  if (e.key === 'Tab') { e.preventDefault(); cpalQ.focus(); }  // one field: focus stays in the dialog
});
cpal.addEventListener('mousedown', (e) => { if (e.target === cpal) closePalette(true); });
function openPalette() {
  if (!cpal.hidden) { cpalQ.select(); return; }
  palOpener = document.activeElement;
  cpalQ.value = '';
  palSel = 0;
  palPlaces = [];
  cpal.hidden = false;
  renderPalette();
  cpalQ.focus();
}
function closePalette(restore) {
  if (cpal.hidden) return;
  cpal.hidden = true;
  if (restore && palOpener && document.contains(palOpener)) palOpener.focus({ preventScroll: true });
  palOpener = null;
}
document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    if (cpal.hidden) openPalette(); else closePalette(true);
  }
});

// Escape closes the innermost thing first: an open popup before the
// details pane behind it (the pane's own handler runs after this one).
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape' || !cpal.hidden) return;
  const pop = map._popup;
  if (pop && pop.isOpen() && !inspectorEl.contains(document.activeElement)) {
    map.closePopup();
    e.stopPropagation();
  }
}, true);
