/* How a plugin's alerts look, everywhere they show.
 *
 * Official agency data is drawn as dots. A plugin alert is a small
 * rounded badge instead: the picture says what the alert is, the color
 * says which plugin it came from. One place decides both, so the map,
 * the Layers list and the popup always agree.
 *
 * csPlugin.color(sourceId)        the plugin's color
 * csPlugin.category(flareKind)    police, crash, hazard, camera, ...
 * csPlugin.badge(sourceId, kind)  HTML for a badge (map, lists)
 * csPlugin.icon(marker)           a Leaflet icon for one alert
 */
(function () {
  // The plugins CommuteScout runs get fixed colors; any other plugin
  // gets one from its id, so it is the same on every visit.
  const KNOWN = { 'wz-flare': '#1d4ed8', 'osm-cameras': '#ea580c' };
  const PALETTE = ['#7c3aed', '#0f766e', '#be123c', '#4d7c0f', '#a16207', '#0369a1'];
  function color(sid) {
    if (KNOWN[sid]) return KNOWN[sid];
    let h = 0;
    for (const c of String(sid || '')) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    return PALETTE[h % PALETTE.length];
  }

  function category(kind) {
    const k = String(kind || '');
    if (k.startsWith('POLICE')) return 'police';
    if (k.startsWith('CRASH')) return 'crash';
    if (k.startsWith('CAMERA')) return 'camera';
    if (k.startsWith('JAM')) return 'jam';
    if (k.startsWith('WEATHER')) return 'weather';
    if (k.startsWith('ROAD_CLOSED') || k.startsWith('LANE_CLOSED') || k.startsWith('RAMP_CLOSED')) return 'closed';
    if (k.startsWith('CHAINS')) return 'chains';
    if (k.startsWith('HAZARD')) return 'hazard';
    return 'other';
  }

  // One 24 by 24 line drawing per category, stroked in white.
  const GLYPH = {
    police: 'M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z',
    crash: 'M4 15l1.5-5h13L20 15M4 15v3h2v-2h12v2h2v-3M8 13h.01M16 13h.01',
    hazard: 'M12 4l9 16H3zM12 10v5M12 17.5v.01',
    camera: 'M4 8h3l2-3h6l2 3h3v11H4zM12 17a3.5 3.5 0 100-7 3.5 3.5 0 000 7z',
    jam: 'M4 7h16M4 12h11M4 17h7',
    weather: 'M7 18h10a4 4 0 000-8 6 6 0 00-11.5 1.5A3.5 3.5 0 007 18z',
    closed: 'M12 21a9 9 0 100-18 9 9 0 000 18zM7 12h10',
    chains: 'M9 15l6-6M10 7l1-1a4 4 0 015.6 5.6l-1 1M14 17l-1 1a4 4 0 01-5.6-5.6l1-1',
    other: 'M12 14.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z',
    // Official kinds, for the inspector's header.
    incident: 'M12 8v5M12 16.5v.01M12 21a9 9 0 100-18 9 9 0 000 18z',
    fire: 'M12 3c1 4 5 5.5 5 10a5 5 0 01-10 0c0-2 1-3.5 2-4.5.5 2 1.5 2.5 2 2.5 0-3 0-5 1-8z',
    snow: 'M12 3v18M4.2 7.5l15.6 9M19.8 7.5l-15.6 9',
    thermo: 'M10 14V5a2 2 0 114 0v9a4 4 0 11-4 0z',
    toll: 'M12 3v18M16 7.5c0-1.7-1.8-2.5-4-2.5s-4 1-4 3 1.8 2.8 4 3.3 4 1.3 4 3.4-1.8 3.3-4 3.3-4-1-4-2.8',
    video: 'M4 7h11v10H4zM15 10.5l5-3v9l-5-3',
    sign: 'M4 5h16v10H4zM8 9h8M8 12h5M12 15v5',
  };
  function svg(cat) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="' +
      (GLYPH[cat] || GLYPH.other) + '"/></svg>';
  }

  // kind may be a Flare kind, or null for "this plugin in general".
  function badge(sid, kind, extraClass) {
    return '<span class="pbadge' + (extraClass ? ' ' + extraClass : '') +
      '" style="--pc:' + color(sid) + '">' + (kind ? svg(category(kind)) : '') + '</span>';
  }

  function sourceId(m) {
    return m.source_id || String(m.id || '').split(':')[0];
  }

  function icon(m) {
    return L.divIcon({ className: 'pbadge-pin', html: badge(sourceId(m), m.flare_kind || 'OTHER'),
      iconSize: [26, 26], iconAnchor: [13, 13], popupAnchor: [0, -12] });
  }

  // The one picture that stands for a whole plugin: its kind when it
  // only ever shows one category, otherwise a plain colored tile.
  function kindFor(kinds) {
    const cats = new Set((kinds || []).map(category));
    return cats.size === 1 ? kinds[0] : null;
  }

  window.csPlugin = { color, category, badge, icon, sourceId, kindFor, svg };
})();
