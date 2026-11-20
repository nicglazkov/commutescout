import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js';
import {
  getAuth, GoogleAuthProvider, signInWithPopup, signOut,
  isSignInWithEmailLink, signInWithEmailLink,
  onAuthStateChanged,
} from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js';

// Watch areas: sign-in, drawing, the list, push. One module for the
// /watch page and the map page's Watch tool. `opts.map` is the Leaflet
// map to draw on; `opts.active()` says whether drawing clicks count.
export async function initWatch(opts) {
  let fittedOnce = false;
  // "Watch this stretch" from the map: the center waits until the
  // viewer is signed in and approved, then lands as a circle.
  let pendingCenter = null;
  function watchHere(lat, lon) {
    pendingCenter = [lat, lon];
    applyPending();
  }
  function applyPending() {
    if (!pendingCenter || !me || me.status !== 'approved') return;
    setMode('circle');
    center = pendingCenter;
    pendingCenter = null;
    redraw();
    map.setView(center, Math.max(map.getZoom(), 10));
    msg('createmsg', 'Center placed. Set the radius, name it, and create the watch.', 'ok');
  }
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[<>&"]/g,
    (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]));
  const show = (id) => ['signin', 'gate', 'appzone']
    .forEach((s) => $(s).classList.toggle('hidden', s !== id));
  const msg = (id, text, cls) => {
    const el = $(id); el.textContent = text || '';
    el.className = 'msg' + (cls ? ' ' + cls : '');
  };

  const cfgRes = await fetch('/api/watch/config');
  const CFG = cfgRes.ok ? await cfgRes.json() : null;
  if (!CFG || !CFG.firebase) {
    show('signin');
    msg('signinmsg', 'Could not load sign-in configuration - refresh to try again.', 'err');
    return null;
  }
  const fb = initializeApp(CFG.firebase);
  const auth = getAuth(fb);
  let user = null;

  async function api(path, options = {}) {
    const token = await user.getIdToken();
    const res = await fetch(path, {
      ...options,
      headers: { Authorization: 'Bearer ' + token,
                 'Content-Type': 'application/json',
                 ...(options.headers || {}) },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || ('request failed (' + res.status + ')'));
    return data;
  }

  // ------------------------------------------------------------- terms

  // Signing in can create an account (Google and email link both do on
  // first use), and the page cannot tell a new account from a returning
  // one until after it exists. So the agreement is asked per browser:
  // an unticked "I agree" box, with every sign-in button disabled until
  // it is ticked. Once agreed here, the box becomes a passive line. The
  // account records the acceptance (/api/me/terms) right after sign-in;
  // an account without one (an email link opened in another browser, an
  // account from before the box) is asked once more before going on.
  const TERMS_VERSION = CFG.termsVersion || '2026-11-19';
  const TERMS_KEY = 'cs.terms';
  const agreedHere = () => {
    try { return localStorage.getItem(TERMS_KEY) === TERMS_VERSION; } catch (e) { return false; }
  };
  const noteAgreed = () => {
    try { localStorage.setItem(TERMS_KEY, TERMS_VERSION); } catch (e) { /* private mode */ }
  };
  // gate: signed in already, only the agreement is missing.
  let termsGate = false;
  function syncAgree() {
    const passive = agreedHere() && !termsGate;
    $('agreerow').hidden = passive;
    $('agreenote').hidden = !passive;
    const ok = passive || $('agree').checked;
    $('googlebtn').disabled = !ok;
    $('emailbtn').disabled = !ok;
    $('termsbtn').disabled = !$('agree').checked;
    $('signinbtns').classList.toggle('hidden', termsGate);
    $('termsbtn').classList.toggle('hidden', !termsGate);
    // Signed in, agreement missing: the page shows only the agreement.
    $('signin').classList.toggle('consent', termsGate);
  }
  $('agree').addEventListener('change', syncAgree);
  syncAgree();
  const mayStart = () => agreedHere() || $('agree').checked;

  // ------------------------------------------------------------- sign-in

  $('googlebtn').addEventListener('click', async () => {
    if (!mayStart()) { msg('signinmsg', 'Tick "I agree" first.', 'err'); return; }
    noteAgreed();
    try { await signInWithPopup(auth, new GoogleAuthProvider()); }
    catch (e) { msg('signinmsg', e.message, 'err'); }
  });

  $('emailbtn').addEventListener('click', async () => {
    const email = $('email').value.trim();
    if (!email) { msg('signinmsg', 'Enter your email first.', 'err'); return; }
    if (!mayStart()) { msg('signinmsg', 'Tick "I agree" first.', 'err'); return; }
    noteAgreed();
    try {
      // Our endpoint mints the link and sends a branded email through
      // Resend, instead of Firebase sending its own unbranded one. The
      // return link still completes below via signInWithEmailLink.
      const r = await fetch('/api/signin-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ email: email, website: '' }),
      });
      const txt = (await r.text()).trim();
      if (r.ok) {
        localStorage.setItem('watchEmail', email);
        msg('signinmsg', txt || 'Link sent - check your inbox.', 'ok');
      } else {
        msg('signinmsg', txt || 'Could not send the link.', 'err');
      }
    } catch (e) { msg('signinmsg', 'Network error. Try again.', 'err'); }
  });

  if (isSignInWithEmailLink(auth, location.href)) {
    const email = localStorage.getItem('watchEmail')
      || prompt('Confirm your email to finish signing in');
    if (email) {
      try {
        await signInWithEmailLink(auth, email, location.href);
        history.replaceState(null, '', location.pathname);
      } catch (e) { msg('signinmsg', e.message, 'err'); }
    }
  }

  // --------------------------------------------------------------- state

  let me = null;

  async function refresh() {
    me = await api('/api/watch/me');
    $('who').innerHTML = '';
    const label = document.createElement('span');
    label.textContent = me.email || 'signed in';
    const out = document.createElement('button');
    out.textContent = 'Sign out';
    out.addEventListener('click', () => signOut(auth));
    $('who').append(label, out);
    const terms = me.terms || {};
    if (terms.version !== TERMS_VERSION) {
      if (agreedHere()) {
        // Ticked here before signing in: the account records it now.
        try { me.terms = (await api('/api/me/terms', { method: 'POST',
          body: JSON.stringify({ version: TERMS_VERSION }) })).terms; } catch (e) { /* next sign-in retries */ }
      } else {
        termsGate = true;
        $('agree').checked = false;
        syncAgree();
        show('signin');
        msg('signinmsg', 'Signed in as ' + (me.email || 'you')
          + '. Agree to the Terms of Use and Privacy Policy to continue.');
        return;
      }
    }
    termsGate = false;
    syncAgree();
    if ($('acctcard')) $('acctcard').hidden = false;
    if ($('acctnote')) $('acctnote').hidden = true;
    if ($('keycard')) { $('keycard').hidden = false; renderKeys(); }
    if (me.prefs && me.prefs.units && window.csUnits
        && me.prefs.units !== window.csUnits.get()) {
      window.csUnits.set(me.prefs.units, { fromServer: true });
    }
    if (me.status === 'approved') {
      show('appzone');
      if (CFG.emailEnabled) $('emailchan').classList.remove('hidden');
      renderWatches();
      applyPending();
      setTimeout(() => map.invalidateSize(), 60);
    } else {
      $('gatetext').textContent = me.status === 'revoked'
        ? 'Access for this account has been turned off. Enter a new access code to re-enable it.'
        : 'Watch areas are in a limited trial. Enter an access code to unlock them.';
      show('gate');
    }
  }

  // The map page's report form and confirm votes need a token; the
  // module owns sign-in, so it lends one out.
  window.csAuth = { token: async () => (user ? user.getIdToken() : null) };
  $('termsbtn').addEventListener('click', async () => {
    if (!$('agree').checked) return;
    noteAgreed();
    msg('signinmsg', '');
    try { await refresh(); } catch (e) { msg('signinmsg', e.message, 'err'); }
  });
  onAuthStateChanged(auth, async (u) => {
    user = u;
    // The map page's Your places follows the account while signed in.
    document.dispatchEvent(new CustomEvent('cs-auth', { detail: { signedIn: !!u } }));
    if (!u) {
      termsGate = false;
      syncAgree();
      $('who').innerHTML = '';
      if ($('acctcard')) $('acctcard').hidden = true;
      if ($('acctnote')) $('acctnote').hidden = false;
      if ($('keycard')) $('keycard').hidden = true;
      show('signin');
      return;
    }
    try { await refresh(); }
    catch (e) { show('signin'); msg('signinmsg', e.message, 'err'); }
  });

  $('redeembtn').addEventListener('click', async () => {
    try {
      await api('/api/watch/redeem', { method: 'POST',
        body: JSON.stringify({ code: $('code').value.trim() }) });
      await refresh();
    } catch (e) { msg('gatemsg', e.message, 'err'); }
  });

  // ----------------------------------------------------------------- map

  // The page hands in its map: /watch draws on its own, the map page on
  // the live map while the Watch tool is open.
  const map = opts.map;
  const active = opts.active || (() => true);
  const drawLayer = L.layerGroup();
  const handleLayer = L.layerGroup();
  const routeLayer = L.layerGroup();
  const savedLayer = L.layerGroup();
  let visible = false;
  function setVisible(on) {
    on = !!on;
    if (on === visible) return;
    visible = on;
    for (const l of [savedLayer, drawLayer, routeLayer, handleLayer]) {
      if (on) l.addTo(map); else map.removeLayer(l);
    }
    if (on && !fittedOnce) fitSaved();
  }

  const LIMITS = CFG.limits || {};
  let mode = 'circle';
  let center = null;
  let polyPoints = [];
  let polyRef = null;
  // A saved watch whose shape (polygon) or route is open on the map.
  let editingShape = null;
  const MAX_PTS = LIMITS.polygon_points || 20;
  // Stops on a route, start and end included. The server enforces the
  // same number (watch.MAX_ROUTE_STOPS) and sends it in the config.
  const MAX_STOPS = LIMITS.route_stops || 8;

  // Where a watch may be drawn: the server's California outline plus the
  // bounds of every state with road data, both served in the config so
  // this page never carries its own copy. Corners can't leave coverage
  // in the first place.
  const COVERAGE = CFG.coverage || { california: [], states: [] };
  function insidePolygon(lat, lon, ring) {
    let inside = false;
    let j = ring.length - 1;
    for (let i = 0; i < ring.length; i++) {
      const [yi, xi] = ring[i];
      const [yj, xj] = ring[j];
      if (((xi > lon) !== (xj > lon)) &&
          (lat < (yj - yi) * (lon - xi) / ((xj - xi) || 1e-12) + yi)) {
        inside = !inside;
      }
      j = i;
    }
    return inside;
  }
  function insideCoverage(lat, lon) {
    if (insidePolygon(lat, lon, COVERAGE.california)) return true;
    return COVERAGE.states.some(({ bounds: b }) =>
      lat >= b[0] && lat <= b[2] && lon >= b[1] && lon <= b[3]);
  }

  const HINTS = {
    circle: 'Click the map to place the center, then set the radius.',
    polygon: 'Tap the map to add corners (3-' + MAX_PTS + '). Drag a corner to move it, '
      + 'tap it to remove it, tap a faint dot between corners to add one there.',
    route: 'Type a start and a destination, or tap the map to drop them. '
      + 'Add stops in between, up to ' + MAX_STOPS + ' in all.',
  };

  function vertexIcon(mid) {
    return L.divIcon({ className: mid ? 'mhandle' : 'vhandle',
      iconSize: mid ? [13, 13] : [17, 17] });
  }

  function rebuildHandles() {
    handleLayer.clearLayers();
    if (mode !== 'polygon') return;
    polyPoints.forEach((pt, i) => {
      const h = L.marker(pt, { icon: vertexIcon(false), draggable: true });
      h.on('drag', (e) => {
        // Corners stop at the state line (the ocean side is open).
        if (!insideCoverage(e.latlng.lat, e.latlng.lng)) {
          h.setLatLng(polyPoints[i]);
          return;
        }
        polyPoints[i] = [e.latlng.lat, e.latlng.lng];
        if (polyRef) polyRef.setLatLngs(polyPoints);
      });
      h.on('dragend', redraw);
      h.on('click', () => { polyPoints.splice(i, 1); redraw(); });
      h.addTo(handleLayer);
    });
    const n = polyPoints.length;
    if (n >= 2 && n < MAX_PTS) {
      const edges = n >= 3 ? n : n - 1;
      for (let i = 0; i < edges; i++) {
        const a = polyPoints[i], b = polyPoints[(i + 1) % n];
        const mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
        const h = L.marker(mid, { icon: vertexIcon(true) });
        h.on('click', () => { polyPoints.splice(i + 1, 0, mid); redraw(); });
        h.addTo(handleLayer);
      }
    }
  }

  function redraw() {
    drawLayer.clearLayers();
    polyRef = null;
    if (mode === 'circle' && center) {
      L.circleMarker(center, { radius: 5, color: '#fff', weight: 1.5,
        fillColor: '#2f81f7', fillOpacity: 1 }).addTo(drawLayer);
      L.circle(center, { radius: radiusKm() * 1000,
        color: '#2f81f7', weight: 2, fillColor: '#2f81f7', fillOpacity: 0.12 })
        .addTo(drawLayer);
    }
    if (mode === 'polygon' && polyPoints.length > 1) {
      polyRef = L.polygon(polyPoints, { color: '#2f81f7', weight: 2,
        fillColor: '#2f81f7', fillOpacity: 0.12 }).addTo(drawLayer);
    }
    rebuildHandles();
    // One way back to a blank map in every mode: "Start over" for a
    // circle or a shape (routes have their own "Clear route").
    const drawn = (mode === 'polygon' && polyPoints.length) || (mode === 'circle' && center);
    $('polytools').classList.toggle('hidden', !drawn || !!(editingShape && mode === 'circle'));
    $('undopt').classList.toggle('hidden', mode !== 'polygon');
    shapeChanged();
  }

  map.on('click', (e) => {
    if (!active()) return;
    const p = [e.latlng.lat, e.latlng.lng];
    if (!insideCoverage(p[0], p[1])) {
      msg('createmsg', 'Watches stay inside a covered state (offshore California is fine).', 'err');
      return;
    }
    msg('createmsg', '');
    if (mode === 'route') { dropStop(p); return; }
    if (mode === 'circle') center = p;
    else if (polyPoints.length < MAX_PTS) polyPoints.push(p);
    redraw();
  });

  $('undopt').addEventListener('click', () => {
    polyPoints.pop(); redraw();
  });
  $('clearpts').addEventListener('click', () => {
    if (mode === 'circle') center = null; else polyPoints = [];
    redraw();
    msg('createmsg', '');
  });

  function startShapeEdit(w) {
    setMode('polygon');
    editingShape = { id: w.id, name: w.name, type: 'polygon' };
    polyPoints = (w.points || []).map(
      (pt) => Array.isArray(pt) ? pt.slice() : [pt.lat, pt.lon]);
    $('shapehint').textContent = 'Editing the shape of “' + w.name
      + '”. Drag corners, tap one to remove it, tap a faint dot to '
      + 'add one, tap the map to append at the end.';
    beginEdit('Save shape');
    redraw();
    if (polyPoints.length > 1) {
      map.fitBounds(L.polygon(polyPoints).getBounds().pad(0.4));
    }
  }

  function beginEdit(saveLabel) {
    $('createbtn').textContent = saveLabel;
    $('canceledit').textContent = 'Cancel editing';
    $('canceledit').classList.remove('hidden');
    // The create form's own name, kinds and filters do not apply to an
    // edit (the row's editor has those); hide them so it is clear what
    // the save button saves.
    document.querySelectorAll('.newwatch-card [data-createonly]')
      .forEach((el) => { el.hidden = true; });
    if ($('wmap')) $('wmap').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function endShapeEdit() {
    editingShape = null;
    $('createbtn').textContent = 'Create watch';
    $('canceledit').classList.add('hidden');
    document.querySelectorAll('.newwatch-card [data-createonly]')
      .forEach((el) => { el.hidden = false; });
    setMode('circle');
  }

  $('canceledit').addEventListener('click', endShapeEdit);

  function setMode(m) {
    if (editingShape) {
      editingShape = null;
      $('createbtn').textContent = 'Create watch';
      $('canceledit').classList.add('hidden');
      document.querySelectorAll('.newwatch-card [data-createonly]')
        .forEach((el) => { el.hidden = false; });
    }
    mode = m;
    $('mode-circle').classList.toggle('on', m === 'circle');
    $('mode-polygon').classList.toggle('on', m === 'polygon');
    $('mode-route').classList.toggle('on', m === 'route');
    for (const k of ['circle', 'polygon', 'route']) {
      $('mode-' + k).setAttribute('aria-pressed', String(m === k));
    }
    $('radiusrow').classList.toggle('hidden', m !== 'circle');
    $('routerow').classList.toggle('hidden', m !== 'route');
    $('shapehint').textContent = HINTS[m];
    center = null; polyPoints = [];
    clearRoute(false);
    redraw();
  }
  $('mode-route').addEventListener('click', () => setMode('route'));

  // Valhalla (Stadia's router) encodes geometry as a precision-6
  // polyline; same decoder as map.html.
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

  async function geocodeOne(q) {
    const res = await fetch('/api/geocode?q=' + encodeURIComponent(q));
    if (!res.ok) throw new Error('address lookup failed');
    const c = ((await res.json()).candidates || [])[0];
    if (!c) throw new Error('Could not find “' + q + '”. Try a fuller address.');
    return c;
  }

  function haversineKm(a, b) {
    const r = Math.PI / 180;
    const dLat = (b[0] - a[0]) * r, dLon = (b[1] - a[1]) * r;
    const h = Math.sin(dLat / 2) ** 2
      + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLon / 2) ** 2;
    return 12742 * Math.asin(Math.sqrt(h));
  }
  const thin = (pts, n) => (pts.length <= n ? pts
    : pts.filter((_, i) => i % Math.ceil(pts.length / n) === 0).concat([pts[pts.length - 1]]));

  // ---------------------------------------------------------- route stops
  // A route watch is built from stops, start and end included, the way
  // directions with stops work in a maps app: type each one (with place
  // suggestions) or tap the map to drop it, drag to reorder, add more at
  // any time. The route is fetched again after every change.
  let stops = [];
  let routePts = null;
  let routeKm = 0;
  let routeDirty = false;
  let autoName = '';
  let routeSeq = 0;
  const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  const emptyStop = () => ({ q: '', lat: null, lon: null });
  const filledStops = () => stops.filter((s) => s.lat != null || s.q.trim());
  const pinLabel = (p) => 'Pin at ' + p[0].toFixed(4) + ', ' + p[1].toFixed(4);
  const stopRole = (i) => (i === 0 ? 'start' : i === stops.length - 1 ? 'destination' : '');
  const stopName = (i) => 'Stop ' + LETTERS[i] + (stopRole(i) ? ', ' + stopRole(i) : '');

  const routeRow = $('routerow');
  // Older markup (the map page's Watch pane) carries From and To fields
  // and a Preview button; the stops editor takes their place. Only the
  // buffer slider stays.
  (function stripLegacyRouteFields() {
    let keep = $('rw-buffer');
    while (keep && keep.parentElement !== routeRow) keep = keep.parentElement;
    for (const child of [...routeRow.children]) {
      if (child === keep) continue;
      if (child.tagName === 'LABEL' && child.htmlFor === 'rw-buffer') continue;
      child.remove();
    }
  })();
  const ICON_PATHS = {
    grip: '<circle cx="9" cy="6" r="1.4"/><circle cx="15" cy="6" r="1.4"/><circle cx="9" cy="12" r="1.4"/>'
      + '<circle cx="15" cy="12" r="1.4"/><circle cx="9" cy="18" r="1.4"/><circle cx="15" cy="18" r="1.4"/>',
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    swap: '<path d="M7 4v16M7 20l-3-3M7 20l3-3M17 20V4M17 4l-3 3M17 4l3 3"/>',
    clear: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  };
  const svg = (name, fill) => '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" '
    + (fill ? 'fill="currentColor" stroke="none"' : 'fill="none" stroke="currentColor" stroke-width="1.75" '
      + 'stroke-linecap="round" stroke-linejoin="round"') + '>' + ICON_PATHS[name] + '</svg>';
  const stopsBox = document.createElement('div');
  stopsBox.className = 'wstops';
  stopsBox.innerHTML = '<div class="wstops-head"><span class="wstops-title" id="wstops-title">Stops</span>'
    + '<span class="wstops-count"></span></div>'
    + '<ol class="wstops-list" aria-labelledby="wstops-title"></ol>'
    + '<div class="wstops-actions">'
    + '<button type="button" class="wstops-btn wstops-add">' + svg('plus') + '<span>Add stop</span></button>'
    + '<button type="button" class="wstops-btn wstops-rev">' + svg('swap') + '<span>Reverse</span></button>'
    + '<button type="button" class="wstops-btn wstops-clear">' + svg('clear') + '<span>Clear route</span></button>'
    + '</div>'
    + '<p class="hint wstops-sum" aria-live="polite"></p>'
    + '<div class="wsr" aria-live="assertive"></div>';
  routeRow.prepend(stopsBox);
  const stopList = stopsBox.querySelector('.wstops-list');
  const announce = (t) => { stopsBox.querySelector('.wsr').textContent = t; };

  function renderStops(focus) {
    stopList.innerHTML = '';
    stops.forEach((s, i) => {
      const li = document.createElement('li');
      li.className = 'wstop' + (s.lat != null ? ' set' : '');
      li.dataset.i = i;
      const mark = document.createElement('span');
      mark.className = 'wstop-mark';
      mark.setAttribute('aria-hidden', 'true');
      mark.textContent = LETTERS[i];
      const field = document.createElement('div');
      field.className = 'wstop-field';
      const input = document.createElement('input');
      input.type = 'text';
      input.maxLength = 200;
      input.autocomplete = 'off';
      input.value = s.q;
      input.placeholder = i === 0 ? 'Choose a start, or tap the map'
        : i === stops.length - 1 ? 'Choose a destination' : 'Add a stop';
      input.setAttribute('aria-label', stopName(i));
      input.setAttribute('role', 'combobox');
      input.setAttribute('aria-autocomplete', 'list');
      input.setAttribute('aria-expanded', 'false');
      const list = document.createElement('ul');
      list.className = 'wstop-sugg';
      list.id = 'wsugg-' + i;
      list.setAttribute('role', 'listbox');
      list.setAttribute('aria-label', 'Suggestions for ' + stopName(i));
      list.hidden = true;
      input.setAttribute('aria-controls', list.id);
      field.append(input, list);
      wireSuggest(input, list, i);
      const move = document.createElement('button');
      move.type = 'button';
      move.className = 'wstop-move';
      move.title = 'Drag to reorder';
      move.setAttribute('aria-label', 'Move ' + stopName(i) + '. Use the up and down arrow keys.');
      move.innerHTML = svg('grip', true);
      wireMove(move, li, i);
      const del = document.createElement('button');
      del.type = 'button';
      del.className = 'wstop-del';
      const removes = stops.length > 2;
      del.title = removes ? 'Remove stop' : 'Clear stop';
      del.setAttribute('aria-label', (removes ? 'Remove ' : 'Clear ') + stopName(i));
      del.innerHTML = svg('x');
      del.hidden = !removes && !s.q;
      del.addEventListener('click', () => removeStop(i));
      li.append(mark, field, move, del);
      stopList.append(li);
    });
    const n = stops.length;
    stopsBox.querySelector('.wstops-count').textContent = n + ' of ' + MAX_STOPS;
    const add = stopsBox.querySelector('.wstops-add');
    add.disabled = n >= MAX_STOPS;
    add.querySelector('span').textContent = n >= MAX_STOPS ? MAX_STOPS + ' stops is the limit' : 'Add stop';
    stopsBox.querySelector('.wstops-rev').disabled = filledStops().length < 2;
    stopsBox.querySelector('.wstops-clear').disabled = !filledStops().length;
    if (focus) {
      const el = stopList.querySelector('li[data-i="' + focus.i + '"] ' + focus.sel);
      if (el) el.focus();
    }
    updateRouteSummary();
  }

  function updateRouteSummary() {
    const el = stopsBox.querySelector('.wstops-sum');
    const fmt = (km, d) => (U ? U.fmt(km, d) : Math.round(km) + ' km');
    const capKm = LIMITS.free_route_km;
    if (routePts) {
      const over = capKm && routeKm > capKm;
      el.textContent = fmt(routeKm, 0) + ' through ' + filledStops().length + ' stops'
        + (capKm ? ' · the limit is ' + fmt(capKm, 0) : '') + (over ? '. Remove a stop or move one closer.' : '');
      el.classList.toggle('over', !!over);
    } else {
      el.textContent = 'Up to ' + MAX_STOPS + ' stops, start and end included'
        + (capKm ? ', on a route up to ' + fmt(capKm, 0) + ' long' : '') + '.';
      el.classList.remove('over');
    }
  }

  function removeStop(i) {
    if (stops.length > 2) stops.splice(i, 1); else stops[i] = emptyStop();
    routeDirty = true;
    renderStops({ i: Math.min(i, stops.length - 1), sel: 'input' });
    scheduleRoute();
  }

  function moveStop(from, to) {
    if (to < 0 || to >= stops.length || from === to) return;
    const [s] = stops.splice(from, 1);
    stops.splice(to, 0, s);
    routeDirty = true;
    renderStops({ i: to, sel: '.wstop-move' });
    announce((s.q || 'Empty stop') + ' is now stop ' + LETTERS[to] + ' of ' + stops.length + '.');
    scheduleRoute();
  }

  // Reorder by dragging the grip (mouse, pen or touch) or with the
  // arrow keys while the grip has focus.
  function wireMove(btn, li, i) {
    btn.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowUp') { e.preventDefault(); moveStop(i, i - 1); }
      if (e.key === 'ArrowDown') { e.preventDefault(); moveStop(i, i + 1); }
    });
    btn.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      btn.setPointerCapture(e.pointerId);
      li.classList.add('dragging');
      const rows = [...stopList.children];
      const startY = e.clientY;
      let target = i;
      const onMove = (ev) => {
        const dy = ev.clientY - startY;
        li.style.transform = 'translateY(' + dy + 'px)';
        target = i;
        rows.forEach((r, j) => {
          if (r === li) return;
          const box = r.getBoundingClientRect();
          const mid = box.top + box.height / 2;
          if (j > i && ev.clientY > mid) target = Math.max(target, j);
          if (j < i && ev.clientY < mid) target = Math.min(target, j);
        });
        rows.forEach((r, j) => {
          if (r === li) return;
          const h = li.getBoundingClientRect().height + 6;
          const shift = (j > i && j <= target) ? -h : (j < i && j >= target) ? h : 0;
          r.style.transform = shift ? 'translateY(' + shift + 'px)' : '';
        });
      };
      const onUp = () => {
        btn.removeEventListener('pointermove', onMove);
        btn.removeEventListener('pointerup', onUp);
        btn.removeEventListener('pointercancel', onUp);
        rows.forEach((r) => { r.style.transform = ''; });
        li.classList.remove('dragging');
        if (target !== i) moveStop(i, target);
      };
      btn.addEventListener('pointermove', onMove);
      btn.addEventListener('pointerup', onUp);
      btn.addEventListener('pointercancel', onUp);
    });
  }

  // Place suggestions as you type, from the same search the map's
  // route planner uses; a typed entry with no pick is looked up when
  // the route is fetched.
  function wireSuggest(input, list, i) {
    let timer = null;
    let items = [];
    let at = -1;
    const close = () => {
      list.hidden = true; list.innerHTML = ''; items = []; at = -1;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
    };
    const pick = (c) => {
      stops[i] = { q: c.name, lat: c.lat, lon: c.lon };
      routeDirty = true;
      close();
      input.value = c.name;
      renderStops();
      scheduleRoute();
      // Next empty stop, so a route can be typed start to end.
      const next = stops.findIndex((s) => !s.q && s.lat == null);
      if (next >= 0) stopList.querySelector('li[data-i="' + next + '"] input')?.focus();
    };
    const highlight = (j) => {
      at = j;
      [...list.children].forEach((li, k) => li.setAttribute('aria-selected', String(k === j)));
      if (j >= 0) input.setAttribute('aria-activedescendant', list.children[j].id);
      else input.removeAttribute('aria-activedescendant');
    };
    input.addEventListener('input', () => {
      stops[i] = { q: input.value, lat: null, lon: null };
      routeDirty = true;
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 2) { close(); return; }
      timer = setTimeout(async () => {
        try {
          const c = map.getCenter();
          const r = await fetch('/api/suggest?q=' + encodeURIComponent(q)
            + '&lat=' + c.lat.toFixed(3) + '&lon=' + c.lng.toFixed(3));
          if (!r.ok || input.value.trim() !== q) return;
          items = ((await r.json()).suggestions || []).slice(0, 6);
        } catch (e) { items = []; }
        list.innerHTML = '';
        items.forEach((c, k) => {
          const li = document.createElement('li');
          li.id = list.id + '-' + k;
          li.setAttribute('role', 'option');
          li.setAttribute('aria-selected', 'false');
          const [head, ...rest] = c.name.split(',');
          const b = document.createElement('b');
          b.textContent = head;
          const sm = document.createElement('span');
          sm.textContent = rest.join(',').trim();
          li.append(b, sm);
          li.addEventListener('pointerdown', (e) => { e.preventDefault(); pick(c); });
          list.append(li);
        });
        list.hidden = !items.length;
        input.setAttribute('aria-expanded', String(!!items.length));
        at = -1;
      }, 180);
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown' && items.length) { e.preventDefault(); highlight((at + 1) % items.length); }
      else if (e.key === 'ArrowUp' && items.length) { e.preventDefault(); highlight(at <= 0 ? items.length - 1 : at - 1); }
      else if (e.key === 'Enter') {
        e.preventDefault();
        if (at >= 0 && items[at]) pick(items[at]);
        else if (items[0]) pick(items[0]);
        else { close(); scheduleRoute(); }
      } else if (e.key === 'Escape' && !list.hidden) { e.preventDefault(); close(); }
    });
    input.addEventListener('blur', () => {
      setTimeout(close, 120);
      if (input.value.trim() && stops[i] && stops[i].lat == null) scheduleRoute();
    });
  }

  function dropStop(p) {
    if (!stops.length) stops = [emptyStop(), emptyStop()];
    let i = stops.findIndex((s) => !s.q && s.lat == null);
    if (i < 0) {
      if (stops.length >= MAX_STOPS) {
        msg('createmsg', 'A route has up to ' + MAX_STOPS + ' stops. Remove one to add another.', 'err');
        return;
      }
      stops.push(emptyStop());
      i = stops.length - 1;
    }
    stops[i] = { q: pinLabel(p), lat: p[0], lon: p[1] };
    routeDirty = true;
    renderStops();
    scheduleRoute();
  }

  function stopIcon(i) {
    return L.divIcon({ className: 'vhandle stopmark', html: '<span>' + LETTERS[i] + '</span>',
      iconSize: [26, 26], iconAnchor: [13, 13] });
  }

  function drawStops() {
    handleLayer.clearLayers();
    if (mode !== 'route') return;
    stops.forEach((s, i) => {
      if (s.lat == null) return;
      const m = L.marker([s.lat, s.lon], { icon: stopIcon(i), draggable: true,
        keyboard: false, title: stopName(i) });
      m.on('dragend', () => {
        const ll = m.getLatLng();
        if (!insideCoverage(ll.lat, ll.lng)) { m.setLatLng([s.lat, s.lon]); return; }
        stops[i] = { q: pinLabel([ll.lat, ll.lng]), lat: ll.lat, lon: ll.lng };
        routeDirty = true;
        renderStops();
        scheduleRoute();
      });
      m.addTo(handleLayer);
    });
  }

  let routeTimer = null;
  function scheduleRoute() {
    clearTimeout(routeTimer);
    routeTimer = setTimeout(computeRoute, 250);
  }

  async function computeRoute() {
    const seq = ++routeSeq;
    for (const s of stops) {
      if (s.lat != null || !s.q.trim()) continue;
      try {
        const c = await geocodeOne(s.q.trim());
        Object.assign(s, { lat: c.lat, lon: c.lon });
      } catch (e) {
        if (seq === routeSeq) msg('createmsg', e.message, 'err');
        return;
      }
    }
    if (seq !== routeSeq) return;
    renderStopsKeepFocus();
    drawStops();
    const located = stops.filter((s) => s.lat != null);
    if (located.length < 2) {
      routePts = null; routeKm = 0;
      routeLayer.clearLayers();
      updateRouteSummary();
      shapeChanged();
      return;
    }
    msg('createmsg', 'Routing…');
    try {
      const res = await fetch('/api/route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          locations: located.map((s) => ({ lat: s.lat, lon: s.lon })),
          preset: 'fastest', units: 'miles',
        }),
      });
      if (!res.ok) throw new Error('The routing service is unavailable. Try again in a moment.');
      const trip = ((await res.json()).routes || [])[0]?.trip;
      if (!trip || !trip.legs || !trip.legs.length) {
        throw new Error('No drivable route links these stops. Move one onto a road.');
      }
      if (seq !== routeSeq) return;
      routePts = trip.legs.flatMap((l) => decodePolyline6(l.shape));
      routeKm = 0;
      for (let k = 1; k < routePts.length; k++) routeKm += haversineKm(routePts[k - 1], routePts[k]);
      drawRouteLine();
      // Name the route after its ends until the user types a name of their own.
      const typed = $('wname').value.trim();
      if (!editingShape && (!typed || typed === autoName)) {
        const first = located[0].q.split(',')[0];
        const last = located[located.length - 1].q.split(',')[0];
        if (!/^Pin at/.test(first) && !/^Pin at/.test(last)) {
          autoName = (first + ' → ' + last).slice(0, 60);
          $('wname').value = autoName;
        }
      }
      msg('createmsg', '');
    } catch (e) {
      if (seq === routeSeq) msg('createmsg', e.message, 'err');
    }
    updateRouteSummary();
    shapeChanged();
  }

  // Re-render without stealing focus from the field being typed in.
  function renderStopsKeepFocus() {
    const a = document.activeElement;
    const li = a && a.closest && a.closest('.wstop');
    if (li && stopList.contains(li)) {
      const sel = a.classList.contains('wstop-move') ? '.wstop-move' : 'input';
      const pos = sel === 'input' ? a.selectionStart : null;
      renderStops({ i: Number(li.dataset.i), sel });
      const now = document.activeElement;
      if (pos != null && now && now.setSelectionRange) now.setSelectionRange(pos, pos);
    } else {
      renderStops();
    }
  }

  function drawRouteLine() {
    routeLayer.clearLayers();
    if (!routePts) return;
    const line = L.polyline(routePts, { color: '#2f81f7', weight: 5, opacity: 0.85 })
      .addTo(routeLayer);
    // Frame the whole route after every change, the way directions do.
    map.fitBounds(line.getBounds().pad(0.15), { maxZoom: 13 });
  }

  function clearRoute(focus) {
    stops = [emptyStop(), emptyStop()];
    routePts = null; routeKm = 0; routeDirty = false;
    routeSeq++;
    routeLayer.clearLayers();
    handleLayer.clearLayers();
    renderStops(focus ? { i: 0, sel: 'input' } : null);
  }

  stopsBox.querySelector('.wstops-add').addEventListener('click', () => {
    if (stops.length >= MAX_STOPS) return;
    stops.push(emptyStop());
    renderStops({ i: stops.length - 1, sel: 'input' });
  });
  stopsBox.querySelector('.wstops-rev').addEventListener('click', () => {
    stops.reverse();
    routeDirty = true;
    renderStops();
    announce('Route reversed.');
    scheduleRoute();
  });
  stopsBox.querySelector('.wstops-clear').addEventListener('click', () => {
    clearRoute(true);
    msg('createmsg', '');
    announce('Route cleared.');
    shapeChanged();
  });

  function startRouteEdit(w) {
    setMode('route');
    editingShape = { id: w.id, name: w.name, type: 'route' };
    const pts = (w.points || []).map((pt) => Array.isArray(pt) ? pt.slice() : [pt.lat, pt.lon]);
    // Watches saved before stops existed keep only their line: its two
    // ends become the first two stops.
    const saved = (w.stops && w.stops.length >= 2) ? w.stops
      : pts.length >= 2 ? [{ lat: pts[0][0], lon: pts[0][1], label: 'Start of saved route' },
        { lat: pts[pts.length - 1][0], lon: pts[pts.length - 1][1], label: 'End of saved route' }]
        : [];
    stops = saved.map((s) => ({ q: s.label || pinLabel([s.lat, s.lon]), lat: s.lat, lon: s.lon }));
    while (stops.length < 2) stops.push(emptyStop());
    routePts = pts.length >= 2 ? pts : null;
    routeKm = w.length_km || 0;
    routeDirty = false;
    const mi = Math.round((w.buffer_km || 3.2) / 1.6);
    $('rw-buffer').value = String(Math.min(2, Math.max(1, mi)));
    $('rw-bufferlabel').textContent = bufferLabel();
    $('shapehint').textContent = 'Editing the route of “' + w.name
      + '”. Add, remove or reorder stops, then save.';
    beginEdit('Save route');
    renderStops();
    drawStops();
    if (routePts) {
      drawRouteLine();
      map.fitBounds(L.polyline(routePts).getBounds().pad(0.2));
    }
    shapeChanged();
  }

  // Units: the radius slider works in the viewer's unit (10 mi or 15 km
  // by default, 25 mi or 40 km at the free cap); the server always
  // gets kilometers. The route buffer slider stays 1 to 2 miles wide
  // and only its label changes.
  const U = window.csUnits;
  const unitLabel = () => (U ? U.label() : 'km');
  const radiusKm = () => (U ? U.toKm(Number($('radius').value)) : Number($('radius').value));
  const bufferLabel = () => {
    const v = Number($('rw-buffer').value);
    return U && U.get() === 'mi' ? v + ' mi' : (v * 1.6).toFixed(1) + ' km';
  };
  // 1.6, not the more precise 1.609: at the 2 mi slider max this lands
  // buffer_km exactly on the 3.2 km free cap instead of just over it,
  // so the top of the slider never gets rejected.
  const bufferKm = () => Number($('rw-buffer').value) * 1.6;
  function applyUnits() {
    const r = $('radius');
    const mi = U && U.get() === 'mi';
    const prev = r.dataset.units;
    if (prev && prev !== unitLabel()) {
      const cur = Number(r.value);
      r.value = String(Math.max(1, Math.round(mi ? cur / 1.609344 : cur * 1.609344)));
    }
    r.max = mi ? '25' : '40';
    if (!prev) r.value = mi ? '10' : '15';
    r.dataset.units = unitLabel();
    $('radiuslabel').textContent = r.value + ' ' + unitLabel();
    $('rw-bufferlabel').textContent = bufferLabel();
    redraw();
    updateRouteSummary();
    if (me && me.status === 'approved') renderWatches();
  }
  $('rw-buffer').addEventListener('input', () => {
    $('rw-bufferlabel').textContent = bufferLabel();
  });
  $('mode-circle').addEventListener('click', () => setMode('circle'));
  $('mode-polygon').addEventListener('click', () => setMode('polygon'));
  $('radius').addEventListener('input', () => {
    $('radiuslabel').textContent = $('radius').value + ' ' + unitLabel();
    redraw();
  });

  // ------------------------------------------------- what to alert about
  // Simple: one chip per kind. Advanced: each kind's report types (the
  // same words everywhere), and under each the exact types the area's
  // own sources use. The server works out which sources cover a shape
  // (/api/watch/options), so a California circle offers CHP's incident
  // types and R-1 to R-3 chain controls, and a shape elsewhere offers
  // that state's own categories.
  const ALERT_KINDS = (CFG.alertKinds && CFG.alertKinds.length) ? CFG.alertKinds : [
    { id: 'incident', label: 'Incidents', subtypes: [] },
    { id: 'closure', label: 'Closures', subtypes: [] },
    { id: 'chain', label: 'Chain controls', subtypes: [] },
    { id: 'fire', label: 'Wildfires', subtypes: [] },
  ];
  const KIND_LABELS = Object.fromEntries(ALERT_KINDS.map((k) => [k.id, k.label]));
  const SUB_LABELS = Object.fromEntries(ALERT_KINDS.map((k) =>
    [k.id, Object.fromEntries((k.subtypes || []).map((s) => [s.id, s.label]))]));
  const DEFAULT_KINDS = ['incident', 'closure', 'fire'];

  function fillKinds(box, selected) {
    box.innerHTML = '';
    for (const k of ALERT_KINDS) {
      const lab = document.createElement('label');
      lab.dataset.kind = k.id;
      if (k.hint) lab.title = k.hint;
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.dataset.kind = k.id;
      cb.checked = selected.includes(k.id);
      lab.append(cb, document.createTextNode(k.label));
      box.append(lab);
    }
  }

  const listJoin = (a) => (a.length < 2 ? a.join('')
    : a.slice(0, -1).join(', ') + (a.length > 2 ? ',' : '') + ' and ' + a[a.length - 1]);

  const optionsCache = new Map();
  function fetchOptions(shape) {
    const key = JSON.stringify(shape);
    if (!optionsCache.has(key)) {
      optionsCache.set(key, api('/api/watch/options', { method: 'POST', body: key })
        .catch(() => { optionsCache.delete(key); return null; }));
    }
    return optionsCache.get(key);
  }

  const round4 = (p) => [Math.round(p[0] * 1e4) / 1e4, Math.round(p[1] * 1e4) / 1e4];
  function shapeOf(w) {
    if (!w) return null;
    if (w.type === 'circle' && w.center) {
      return { type: 'circle', center: { lat: w.center.lat, lon: w.center.lon },
        radius_km: Math.round(w.radius_km * 10) / 10 };
    }
    const pts = (w.points || []).map((pt) => Array.isArray(pt) ? pt : [pt.lat, pt.lon]);
    return pts.length ? { type: w.type, points: thin(pts, 300).map(round4) } : null;
  }
  function currentShape() {
    if (mode === 'circle' && center) {
      return shapeOf({ type: 'circle', center: { lat: round4(center)[0], lon: round4(center)[1] },
        radius_km: radiusKm() });
    }
    if (mode === 'polygon' && polyPoints.length >= 3) return shapeOf({ type: 'polygon', points: polyPoints });
    if (mode === 'route') {
      const pts = routePts || stops.filter((s) => s.lat != null).map((s) => [s.lat, s.lon]);
      if (pts.length) return shapeOf({ type: 'route', points: pts });
    }
    return null;
  }

  let panelSeq = 0;
  function filterPanel({ kindsBox, getShape, initial }) {
    const uid = 'wadv' + (++panelSeq);
    // kind -> { subs: Set, raw: Set }; no entry means every report type.
    const sel = {};
    const load = (f) => {
      for (const k of Object.keys(sel)) delete sel[k];
      for (const [k, v] of Object.entries(f || {})) {
        sel[k] = { subs: new Set(v.subtypes || []), raw: new Set(v.raw || []) };
      }
    };
    load(initial);
    let opts = null;
    let state = 'idle';
    let shownFor = null;
    const openRaw = new Set();
    const el = document.createElement('details');
    el.className = 'wadv';
    const sum = document.createElement('summary');
    sum.innerHTML = '<span class="wadv-t">Advanced</span><span class="wadv-s"></span>';
    const body = document.createElement('div');
    body.className = 'wadv-body';
    el.append(sum, body);

    const checkedKinds = () => [...kindsBox.querySelectorAll('input[data-kind]:checked')]
      .map((c) => c.dataset.kind);
    function info(k) {
      const o = opts && opts.kinds.find((x) => x.id === k);
      if (o) return o;
      const base = ALERT_KINDS.find((x) => x.id === k) || { subtypes: [] };
      return { id: k, label: base.label, available: true,
        subtypes: (base.subtypes || []).map((s) => ({ id: s.id, label: s.label, sources: [] })) };
    }
    const avail = (k) => info(k).subtypes.map((s) => s.id);
    const rawSub = (k) => {
      const m = {};
      for (const s of info(k).subtypes) for (const src of s.sources) for (const t of src.types) m[t.key] = s.id;
      return m;
    };
    function isAll(k) {
      const s = sel[k];
      if (!s) return true;
      if (s.raw.size) return false;
      const a = avail(k);
      return a.length > 0 && a.every((id) => s.subs.has(id));
    }
    function ensure(k) {
      if (!sel[k]) sel[k] = { subs: new Set(avail(k)), raw: new Set() };
      return sel[k];
    }
    function summary() {
      const narrowed = checkedKinds().filter((k) => !isAll(k));
      sum.querySelector('.wadv-s').textContent = narrowed.length
        ? 'Narrowed: ' + narrowed.map((k) => KIND_LABELS[k]).join(', ')
        : 'Every report type';
    }

    function render() {
      summary();
      if (!el.open) return;
      const a = document.activeElement;
      const keep = a && body.contains(a)
        ? ['data-sub', 'data-raw', 'data-all', 'data-none', 'data-more']
          .map((n) => a.getAttribute(n) && '[' + n + '="' + CSS.escape(a.getAttribute(n)) + '"]')
          .find(Boolean)
        : null;
      const keepKind = keep && a.closest('[data-kind]')?.dataset.kind;
      body.innerHTML = '';
      const where = document.createElement('p');
      where.className = 'hint wadv-where';
      where.textContent = !getShape()
        ? 'Draw the area to see the exact types its sources report. Until then these are the report types every area has.'
        : state === 'loading' ? 'Checking which sources cover this area…'
          : opts && opts.states.length
            ? 'This area is in ' + listJoin(opts.states) + '. You get alerts for every ticked type; open a type to pick the exact words its source uses.'
            : opts ? 'No state road feed covers this area yet; weather alerts and wildfires still do.'
              : 'Could not load this area’s sources. Showing the report types every area has.';
      body.append(where);
      const kinds = checkedKinds();
      if (!kinds.length) {
        const p = document.createElement('p');
        p.className = 'hint';
        p.textContent = 'Turn on at least one kind above.';
        body.append(p);
      }
      for (const k of kinds) body.append(kindSection(k));
      if (keep) {
        const sc = keepKind ? body.querySelector('[data-kind="' + keepKind + '"]') : body;
        const el2 = sc && sc.querySelector(keep);
        if (el2) el2.focus();
      }
    }

    function kindSection(k) {
      const i = info(k);
      const s = sel[k];
      const sec = document.createElement('fieldset');
      sec.className = 'wadv-kind';
      sec.dataset.kind = k;
      const lg = document.createElement('legend');
      lg.textContent = KIND_LABELS[k] || k;
      sec.append(lg);
      if (!i.available) {
        const p = document.createElement('p');
        p.className = 'hint';
        p.textContent = 'No source reports ' + (KIND_LABELS[k] || k).toLowerCase()
          + ' in this area today. You will still be alerted if one starts.';
        sec.append(p);
      }
      if (!i.subtypes.length) {
        if (i.available) {
          const p = document.createElement('p');
          p.className = 'hint';
          p.textContent = k === 'chain' ? 'No chain control levels are reported in this area.'
            : 'Every report, no narrower types.';
          sec.append(p);
        }
        return sec;
      }
      const tools = document.createElement('div');
      tools.className = 'wadv-tools';
      const allB = document.createElement('button');
      allB.type = 'button'; allB.textContent = 'All';
      allB.setAttribute('data-all', k);
      allB.setAttribute('aria-label', 'Every ' + (KIND_LABELS[k] || k).toLowerCase() + ' report type');
      allB.addEventListener('click', () => { delete sel[k]; render(); });
      const noneB = document.createElement('button');
      noneB.type = 'button'; noneB.textContent = 'None';
      noneB.setAttribute('data-none', k);
      noneB.setAttribute('aria-label', 'No ' + (KIND_LABELS[k] || k).toLowerCase() + ' report types');
      noneB.addEventListener('click', () => { sel[k] = { subs: new Set(), raw: new Set() }; render(); });
      tools.append(allB, noneB);
      sec.append(tools);
      const ul = document.createElement('ul');
      ul.className = 'wadv-subs';
      for (const st of i.subtypes) {
        const on = !s || s.subs.has(st.id);
        const keys = st.sources.flatMap((src) => src.types.map((t) => t.key));
        const some = !on && s && keys.some((key) => s.raw.has(key));
        const li = document.createElement('li');
        const row = document.createElement('div');
        row.className = 'wadv-row';
        const lab = document.createElement('label');
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.setAttribute('data-sub', st.id);
        cb.checked = on;
        cb.indeterminate = !!some;
        if (some) cb.setAttribute('aria-checked', 'mixed');
        cb.addEventListener('change', () => {
          const x = ensure(k);
          for (const key of keys) x.raw.delete(key);
          if (cb.checked) x.subs.add(st.id); else x.subs.delete(st.id);
          render();
        });
        const txt = document.createElement('span');
        txt.textContent = st.label;
        lab.append(cb, txt);
        row.append(lab);
        li.append(row);
        if (keys.length) {
          const pid = uid + '-' + k + '-' + st.id;
          const open = openRaw.has(k + '/' + st.id);
          const more = document.createElement('button');
          more.type = 'button';
          more.className = 'wadv-more';
          more.setAttribute('data-more', st.id);
          more.setAttribute('aria-expanded', String(open));
          more.setAttribute('aria-controls', pid);
          const n = some ? keys.filter((key) => s.raw.has(key)).length : null;
          more.textContent = (n != null ? n + ' of ' : '') + keys.length
            + (keys.length === 1 ? ' source type' : ' source types');
          more.setAttribute('aria-label', more.textContent + ' for ' + st.label);
          more.addEventListener('click', () => {
            if (open) openRaw.delete(k + '/' + st.id); else openRaw.add(k + '/' + st.id);
            render();
          });
          row.append(more);
          const box = document.createElement('div');
          box.className = 'wadv-raw';
          box.id = pid;
          box.hidden = !open;
          for (const src of st.sources) {
            const g = document.createElement('div');
            g.setAttribute('role', 'group');
            const gl = document.createElement('div');
            gl.className = 'wadv-src';
            gl.id = pid + '-' + src.id;
            gl.textContent = 'From ' + src.label;
            g.setAttribute('aria-labelledby', gl.id);
            g.append(gl);
            for (const t of src.types) {
              const rl = document.createElement('label');
              const rc = document.createElement('input');
              rc.type = 'checkbox';
              rc.setAttribute('data-raw', t.key);
              rc.checked = on || (s && s.raw.has(t.key));
              rc.addEventListener('change', () => {
                const x = ensure(k);
                if (x.subs.has(st.id)) {
                  // Narrowing a whole report type to some of its
                  // source types: keep the others ticked.
                  x.subs.delete(st.id);
                  for (const key of keys) if (key !== t.key) x.raw.add(key);
                } else if (rc.checked) x.raw.add(t.key);
                else x.raw.delete(t.key);
                render();
              });
              const tt = document.createElement('span');
              tt.textContent = t.label;
              rl.append(rc, tt);
              g.append(rl);
            }
            box.append(g);
          }
          li.append(box);
        }
        ul.append(li);
      }
      sec.append(ul);
      return sec;
    }

    async function refresh() {
      summary();
      if (!el.open) return;
      const shape = getShape();
      const key = shape ? JSON.stringify(shape) : null;
      if (key === shownFor && state !== 'loading') { render(); return; }
      shownFor = key;
      if (!shape) { opts = null; state = 'idle'; render(); return; }
      state = 'loading';
      render();
      const r = await fetchOptions(shape);
      if (shownFor !== key) return;
      opts = r;
      state = r ? 'ready' : 'failed';
      // Raw types picked for a source this area does not have would
      // never match here; they stay stored but are not shown.
      render();
    }

    function read() {
      const filters = {};
      for (const k of checkedKinds()) {
        if (isAll(k)) continue;
        const s = sel[k];
        if (!s.subs.size && !s.raw.size) {
          const name = (KIND_LABELS[k] || k).toLowerCase();
          return { error: 'Pick at least one report type for ' + name + ' under Advanced, or turn '
            + name + ' off.' };
        }
        filters[k] = { subtypes: [...s.subs], raw: [...s.raw] };
      }
      return { filters };
    }

    function reset(f) {
      load(f);
      openRaw.clear();
      el.open = false;
      summary();
    }

    el.addEventListener('toggle', refresh);
    kindsBox.addEventListener('change', render);
    summary();
    return { el, refresh, read, reset };
  }

  // The create form's chips and panel.
  const createKinds = [...document.querySelectorAll('.newwatch-card .kinds')]
    .find((b) => !b.closest('.weditor'));
  fillKinds(createKinds, DEFAULT_KINDS);
  const createPanel = filterPanel({ kindsBox: createKinds, getShape: currentShape });
  const kindsField = createKinds.closest('fieldset, .field') || createKinds;
  kindsField.after(createPanel.el);
  // Hidden while a saved watch's shape is edited on the map.
  for (const el of [$('wname').closest('.field') || $('wname'), kindsField, createPanel.el,
    $('ch-push').closest('fieldset, .field')]) {
    if (el) el.setAttribute('data-createonly', '');
  }
  let shapeTimer = null;
  function shapeChanged() {
    clearTimeout(shapeTimer);
    shapeTimer = setTimeout(() => createPanel.refresh(), 450);
  }

  clearRoute(false);
  applyUnits();
  document.addEventListener('cs-units', (e) => {
    applyUnits();
    // Mirror a choice to the account; a value that came from the
    // account is not echoed back.
    if (user && !(e.detail && e.detail.fromServer)) {
      api('/api/watch/prefs', { method: 'POST',
        body: JSON.stringify({ units: e.detail.units }) }).catch(() => {});
    }
  });

  // ------------------------------------------------------------- watches

  async function reloadWatches() {
    me = await api('/api/watch/me');
    renderWatches();
  }

  async function deleteWatch(w) {
    if (!confirm('Delete "' + w.name + '"? Alerts for this area stop immediately.')) return;
    try {
      await api('/api/watch/' + w.id, { method: 'DELETE' });
      if (editingShape && editingShape.id === w.id) endShapeEdit();
      await reloadWatches();
      msg('listmsg', '“' + w.name + '” deleted.', 'ok');
    } catch (err) { msg('listmsg', err.message, 'err'); }
  }

  function watchEditor(w) {
    const form = document.createElement('div');
    form.className = 'weditor';
    const nameIn = document.createElement('input');
    nameIn.type = 'text'; nameIn.maxLength = 60; nameIn.value = w.name || '';
    nameIn.setAttribute('aria-label', 'Name');
    const kindsBox = document.createElement('div');
    kindsBox.className = 'kinds';
    kindsBox.setAttribute('role', 'group');
    kindsBox.setAttribute('aria-label', 'Alert me about');
    fillKinds(kindsBox, w.kinds || []);
    const panel = filterPanel({ kindsBox, getShape: () => shapeOf(w), initial: w.filters });
    const chanBox = document.createElement('div');
    chanBox.className = 'chans';
    chanBox.setAttribute('role', 'group');
    chanBox.setAttribute('aria-label', 'Send alerts by');
    const mkChan = (key, label, checked) => {
      const lab = document.createElement('label');
      const cb = document.createElement('input');
      cb.type = 'checkbox'; cb.dataset.chan = key; cb.checked = checked;
      lab.append(cb, document.createTextNode(label));
      return lab;
    };
    chanBox.append(mkChan('push', 'Push', (w.channels || {}).push !== false));
    if (CFG.emailEnabled) {
      chanBox.append(mkChan('email', 'Email', !!(w.channels || {}).email));
    }
    const save = document.createElement('button');
    save.type = 'button';
    save.className = 'primary'; save.textContent = 'Save changes';
    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.className = 'ghost'; cancel.textContent = 'Cancel';
    save.addEventListener('click', async (e) => {
      e.stopPropagation();
      const kinds = [...kindsBox.querySelectorAll('input:checked')]
        .map((c) => c.dataset.kind);
      if (!kinds.length) { msg('listmsg', 'Pick at least one kind of alert.', 'err'); return; }
      const f = panel.read();
      if (f.error) { msg('listmsg', f.error, 'err'); return; }
      const channels = {};
      for (const cb of chanBox.querySelectorAll('input[data-chan]')) {
        channels[cb.dataset.chan] = cb.checked;
      }
      try {
        await api('/api/watch/' + w.id, { method: 'PATCH',
          body: JSON.stringify({ name: nameIn.value, kinds, filters: f.filters, channels }) });
        await reloadWatches();
        msg('listmsg', 'Saved.', 'ok');
      } catch (err) { msg('listmsg', err.message, 'err'); }
    });
    cancel.addEventListener('click', (e) => {
      e.stopPropagation();
      const toggle = form.closest('.witem')?.querySelector('.wedit');
      form.remove();
      if (toggle) { toggle.setAttribute('aria-expanded', 'false'); toggle.focus(); }
    });
    form.addEventListener('click', (e) => e.stopPropagation());
    const btnRow = document.createElement('div');
    btnRow.className = 'devrow';
    btnRow.append(save, cancel);
    if (w.type === 'polygon' || w.type === 'route') {
      const shapeBtn = document.createElement('button');
      shapeBtn.type = 'button';
      shapeBtn.className = 'ghost';
      shapeBtn.textContent = w.type === 'route' ? 'Edit route on map' : 'Edit shape on map';
      shapeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        form.remove();
        if (w.type === 'route') startRouteEdit(w); else startShapeEdit(w);
      });
      btnRow.append(shapeBtn);
    }
    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'ghost danger wdelete';
    delBtn.textContent = 'Delete watch';
    delBtn.addEventListener('click', (e) => { e.stopPropagation(); deleteWatch(w); });
    btnRow.append(delBtn);
    const cap = (t) => { const d = document.createElement('div');
      d.className = 'wlabel'; d.textContent = t; d.setAttribute('aria-hidden', 'true'); return d; };
    form.append(cap('Name'), nameIn, cap('Alert me about'), kindsBox, panel.el,
      cap('Send alerts by'), chanBox, btnRow);
    return form;
  }

  // Saved areas take the page's "ok" green when it has the site's tokens
  // (the /watch page), so they read in both themes; the map page keeps
  // the darker green it always had.
  const savedColor = () => getComputedStyle(document.documentElement)
    .getPropertyValue('--cs-ok').trim() || '#1c3a2e';
  const ICONS = {
    pause: '<path d="M8 5v14M16 5v14"/>',
    play: '<path d="M7 4.5v15l12-7.5z"/>',
    edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
    del: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  };
  const iconBtn = (icon, label) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.title = label;
    b.setAttribute('aria-label', label);
    b.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" '
      + 'fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" '
      + 'stroke-linejoin="round">' + ICONS[icon] + '</svg>';
    return b;
  };
  document.addEventListener('cs-theme', () => {
    if (me && me.status === 'approved') renderWatches();
  });

  // One chip per kind; a narrowed kind names what it is narrowed to.
  function kindChip(w, k) {
    const chip = document.createElement('span');
    chip.dataset.kind = k;
    const f = (w.filters || {})[k];
    const label = KIND_LABELS[k] || k;
    if (!f) { chip.textContent = label; return chip; }
    const names = (f.subtypes || []).map((s) => (SUB_LABELS[k] || {})[s] || s)
      .concat((f.raw || []).map((r) => r.split('|').slice(1).join('|')));
    const shown = names.slice(0, 2).join(', ') + (names.length > 2 ? ' +' + (names.length - 2) : '');
    chip.classList.add('narrow');
    const b = document.createElement('b');
    b.textContent = label;
    chip.append(b, document.createTextNode(': ' + shown));
    chip.title = label + ': ' + names.join(', ');
    return chip;
  }

  function renderWatches() {
    const list = $('wlist');
    list.innerHTML = '';
    savedLayer.clearLayers();
    const used = me.watches.length;
    const cap = LIMITS.free_watches;
    $('wcount').textContent = used + ' of ' + cap + ' watch areas used';
    $('usagefill').style.width = (cap ? Math.min(100, (used / cap) * 100) : 0) + '%';
    if (!me.watches.length) {
      list.innerHTML = '<div class="empty"><div class="empty-ico"></div>'
        + '<div class="empty-title">No watch areas yet</div>'
        + '<div class="empty-sub">Choose a shape, draw it on the map, '
        + 'then name it to start getting alerts.</div></div>';
      return;
    }
    for (const w of me.watches) {
      const paused = w.active === false;
      const style = paused
        ? { color: '#8a94a3', weight: 1.5, dashArray: '6 6',
            fillColor: '#8a94a3', fillOpacity: 0.05 }
        : { color: savedColor(), weight: 1.5,
            fillColor: savedColor(), fillOpacity: 0.08 };
      let shape;
      if (w.type === 'circle') {
        shape = L.circle([w.center.lat, w.center.lon],
          Object.assign({ radius: w.radius_km * 1000 }, style))
          .addTo(savedLayer);
      } else if (w.type === 'route') {
        const pts = (w.points || []).map(
          (pt) => Array.isArray(pt) ? pt : [pt.lat, pt.lon]);
        shape = L.polyline(pts, Object.assign({}, style,
          { weight: 4, fill: false })).addTo(savedLayer);
      } else {
        const pts = (w.points || []).map(
          (pt) => Array.isArray(pt) ? pt : [pt.lat, pt.lon]);
        shape = L.polygon(pts, style).addTo(savedLayer);
      }
      shape.bindPopup(esc(w.name || 'Watch area') + (paused ? ' (paused)' : ''));
      const row = document.createElement('div');
      row.className = 'witem' + (paused ? ' paused' : '');
      const dot = document.createElement('i');
      dot.style.background = paused ? '#8a94a3' : savedColor();
      const text = document.createElement('div');
      text.className = 'wtext';
      // The name is the row's own button: it frames the area on the map.
      const name = document.createElement('button');
      name.type = 'button';
      name.className = 'wname';
      name.textContent = w.name;
      name.title = 'Show on the map';
      if (paused) {
        const st = document.createElement('span');
        st.className = 'wstate';
        st.textContent = 'Paused';
        name.append(' ', st);
      }
      const meta = document.createElement('div');
      meta.className = 'wmeta';
      const chans = [];
      if ((w.channels || {}).push !== false) chans.push('push');
      if ((w.channels || {}).email) chans.push('email');
      const fmt = (km, d) => (U ? U.fmt(km, d) : Math.round(km) + ' km');
      const nStops = (w.stops || []).length || 2;
      meta.textContent = (w.type === 'circle'
        ? fmt(w.radius_km) + ' circle'
        : w.type === 'route'
          ? fmt(w.length_km || 0, 0) + ' route, ' + nStops + ' stops · '
            + fmt(w.buffer_km || 3, 1) + ' either side'
          : 'Polygon') +
        ' · ' + (chans.length ? chans.join(' and ') : 'no delivery');
      const kindsRow = document.createElement('div');
      kindsRow.className = 'wkinds';
      for (const k of (w.kinds || [])) kindsRow.append(kindChip(w, k));
      text.append(name, meta, kindsRow);
      const pause = iconBtn(paused ? 'play' : 'pause',
        (paused ? 'Resume alerts for ' : 'Pause alerts for ') + w.name);
      pause.addEventListener('click', async (e) => {
        e.stopPropagation();
        try {
          await api('/api/watch/' + w.id, { method: 'PATCH',
            body: JSON.stringify({ active: paused }) });
          await reloadWatches();
        } catch (err) { msg('listmsg', err.message, 'err'); }
      });
      const edit = iconBtn('edit', 'Edit ' + w.name);
      edit.classList.add('wedit');
      edit.setAttribute('aria-expanded', 'false');
      edit.addEventListener('click', (e) => {
        e.stopPropagation();
        const open = row.querySelector('.weditor');
        if (open) { open.remove(); edit.setAttribute('aria-expanded', 'false'); return; }
        row.append(watchEditor(w));
        edit.setAttribute('aria-expanded', 'true');
        row.querySelector('.weditor input').focus();
      });
      const del = iconBtn('del', 'Delete ' + w.name);
      del.addEventListener('click', (e) => { e.stopPropagation(); deleteWatch(w); });
      row.append(dot, text, pause, edit, del);
      name.addEventListener('click', () => {
        map.fitBounds(shape.getBounds().pad(0.3));
      });
      row.addEventListener('click', () => {
        map.fitBounds(shape.getBounds().pad(0.3));
      });
      list.append(row);
    }
    if (!fittedOnce && active()) fitSaved();
  }

  // First sight of the saved areas frames them once. On the map page
  // that waits until the Watch tool is open, so the live view stays put.
  function fitSaved() {
    if (fittedOnce || !savedLayer.getLayers().length) return;
    fittedOnce = true;
    const group = L.featureGroup(savedLayer.getLayers());
    // The map container was hidden until this render. Let Leaflet
    // re-measure it first, or fitBounds computes against a 0x0 map
    // and lands on a world view instead of the watch areas.
    setTimeout(() => {
      map.invalidateSize();
      map.fitBounds(group.getBounds().pad(0.35), { maxZoom: 13 });
    }, 120);
  }

  const stopsPayload = () => stops.filter((s) => s.lat != null)
    .map((s) => ({ lat: s.lat, lon: s.lon, label: s.q.slice(0, 120) }));

  $('createbtn').addEventListener('click', async () => {
    if (editingShape) {
      let body;
      if (editingShape.type === 'route') {
        body = { buffer_km: bufferKm() };
        if (routeDirty) {
          if (!routePts || stopsPayload().length < 2) {
            msg('createmsg', 'A route needs a start and a destination.', 'err');
            return;
          }
          Object.assign(body, { points: routePts, stops: stopsPayload() });
        }
      } else {
        if (polyPoints.length < 3) {
          msg('createmsg', 'A shape needs at least three corners.', 'err');
          return;
        }
        body = { points: polyPoints };
      }
      try {
        await api('/api/watch/' + editingShape.id, { method: 'PATCH',
          body: JSON.stringify(body) });
        const what = editingShape.type === 'route' ? 'Route' : 'Shape';
        endShapeEdit();
        await reloadWatches();
        msg('createmsg', what + ' updated.', 'ok');
      } catch (e) { msg('createmsg', e.message, 'err'); }
      return;
    }
    const kinds = [...createKinds.querySelectorAll('input:checked')]
      .map((c) => c.dataset.kind);
    if (!kinds.length) { msg('createmsg', 'Pick at least one kind of alert.', 'err'); return; }
    const f = createPanel.read();
    if (f.error) { msg('createmsg', f.error, 'err'); return; }
    const body = {
      name: $('wname').value.trim(),
      kinds,
      filters: f.filters,
      channels: { push: $('ch-push').checked, email: $('ch-email').checked },
    };
    if (mode === 'circle') {
      if (!center) { msg('createmsg', 'Click the map to place the center first.', 'err'); return; }
      // The free cap is 40.2 km; 25 mi converts a hair above it.
      const km = radiusKm();
      Object.assign(body, { type: 'circle',
        center: { lat: center[0], lon: center[1] },
        radius_km: Math.min(km, (CFG.limits && CFG.limits.free_radius_km) || km) });
    } else if (mode === 'route') {
      if (!routePts || routePts.length < 2) {
        msg('createmsg', 'Add a start and a destination first.', 'err'); return;
      }
      Object.assign(body, { type: 'route', points: routePts, stops: stopsPayload(),
        buffer_km: bufferKm() });
    } else {
      if (polyPoints.length < 3) { msg('createmsg', 'Add at least three corners on the map.', 'err'); return; }
      Object.assign(body, { type: 'polygon', points: polyPoints });
    }
    try {
      await api('/api/watch/create', { method: 'POST',
        body: JSON.stringify(body) });
      center = null; polyPoints = [];
      clearRoute(false);
      $('wname').value = '';
      fillKinds(createKinds, DEFAULT_KINDS);
      createPanel.reset();
      redraw();
      me = await api('/api/watch/me');
      renderWatches();
      msg('createmsg', 'Watch created.', 'ok');
    } catch (e) { msg('createmsg', e.message, 'err'); }
  });

  // ------------------------------------------------------------ API keys
  // Only the map page's Settings pane has these elements; the module
  // runs on /watch too, so every touch is guarded.
  async function renderKeys() {
    const list = $('keylist');
    if (!list) return;
    try {
      const data = await api('/api/keys');
      list.innerHTML = '';
      if (!data.keys.length) {
        list.innerHTML = '<div class="hint">No keys yet.</div>';
      }
      for (const k of data.keys) {
        const row = document.createElement('div');
        row.className = 'witem keyrow' + (k.revoked ? ' paused' : '');
        const text = document.createElement('div');
        const name = document.createElement('div');
        name.className = 'wname';
        name.textContent = (k.name || 'Unnamed key') + (k.revoked ? ' (revoked)' : '');
        const meta = document.createElement('small');
        meta.textContent = k.prefix + '\u2026 \u00b7 ' + k.tier + ', ' +
          k.daily_limit.toLocaleString() + ' a day' +
          (k.last_used_at ? ' \u00b7 last used ' + new Date(k.last_used_at).toLocaleDateString()
            : ' \u00b7 never used');
        text.append(name, meta);
        row.append(text);
        if (!k.revoked) {
          const del = document.createElement('button');
          del.type = 'button';
          del.textContent = '\u00d7';
          del.title = 'Revoke this key';
          del.addEventListener('click', async (e) => {
            e.stopPropagation();
            if (!confirm('Revoke "' + (k.name || k.prefix) + '"? Requests with it stop immediately.')) return;
            try {
              await api('/api/keys/' + k.id, { method: 'DELETE' });
              await renderKeys();
            } catch (err) { msg('keymsg', err.message, 'err'); }
          });
          row.append(del);
        }
        list.append(row);
      }
    } catch (e) { msg('keymsg', e.message, 'err'); }
  }
  // ------------------------------------------------- connect a new key
  // Steps per AI app come from /api/mcp-setup (connect.py, the same
  // source as /mcp and /llms.txt). The key is filled in here, in the
  // browser; it is never sent anywhere but the clipboard.
  let setupData = null;
  let setupPick = 'chatgpt';
  async function loadSetup() {
    if (!setupData) {
      const r = await fetch('/api/mcp-setup');
      if (!r.ok) throw new Error('setup steps unavailable');
      setupData = await r.json();
    }
    return setupData;
  }
  function el(tag, attrs, text) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
    if (text != null) n.textContent = text;
    return n;
  }
  function installLink(kind, url) {
    if (kind === 'cursor') {
      return 'cursor://anysphere.cursor-deeplink/mcp/install?name=commutescout&config='
        + encodeURIComponent(btoa(JSON.stringify({ url })));
    }
    if (kind === 'vscode') {
      return 'vscode:mcp/install?' + encodeURIComponent(
        JSON.stringify({ name: 'commutescout', type: 'http', url }));
    }
    return null;
  }
  function copyButton(text) {
    const b = el('button', { type: 'button' }, 'Copy');
    b.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(text); b.textContent = 'Copied'; }
      catch (e) { b.textContent = 'Select it'; }
      setTimeout(() => { b.textContent = 'Copy'; }, 1600);
    });
    return b;
  }
  function renderSetup(key) {
    const d = setupData;
    const fill = (t) => t.split(d.key_placeholder).join(key);
    const tiles = $('ktiles');
    tiles.replaceChildren(...d.clients.map((c) => {
      const t = el('button', { type: 'button', class: 'ktile',
        'aria-pressed': String(c.id === setupPick) });
      t.append(el('b', {}, c.short || c.name), el('small', {}, c.hint || ''));
      t.addEventListener('click', () => { setupPick = c.id; renderSetup(key); });
      return t;
    }));
    const c = d.clients.find((x) => x.id === setupPick) || d.clients[0];
    $('kapptitle').textContent = `Add it to ${c.short || c.name}`;
    const body = [];
    const url = fill(d.personal_url);
    const link = c.install && installLink(c.install, url);
    if (link) {
      body.push(el('a', { class: 'kone', href: link },
        `Add to ${c.short || c.name}`));
    }
    for (const step of c.steps) {
      if (step.code) {
        const pre = el('pre', { class: 'ksnip' }, fill(step.code));
        pre.append(copyButton(fill(step.code)));
        body.push(pre);
      } else {
        body.push(el('p', {}, fill(step.text)));
      }
    }
    body.push(el('p', { class: 'knote' }, d.link_note));
    $('kappbody').replaceChildren(...body);
  }
  async function showSetup(key) {
    try { await loadSetup(); renderSetup(key); }
    catch (e) {
      $('kappbody').replaceChildren(el('p', {},
        'See commutescout.com/mcp for setup steps.'));
    }
  }

  if ($('keycreate')) {
    $('keycreate').addEventListener('click', async () => {
      msg('keymsg', '');
      try {
        const r = await api('/api/keys', { method: 'POST',
          body: JSON.stringify({ name: $('keyname').value.trim() }) });
        $('keyvalue').textContent = r.key;
        $('keynew').hidden = false;
        $('keyname').value = '';
        showSetup(r.key);
        await renderKeys();
      } catch (e) { msg('keymsg', e.message, 'err'); }
    });
    $('keycopy').addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText($('keyvalue').textContent);
        $('keycopy').textContent = 'Copied';
        setTimeout(() => { $('keycopy').textContent = 'Copy'; }, 1800);
      } catch (e) { /* the code block is selectable */ }
    });
  }

  // ---------------------------------------------------------------- push

  function b64ToBytes(b64) {
    const pad = '='.repeat((4 - (b64.length % 4)) % 4);
    const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
  }

  $('notifbtn').addEventListener('click', async () => {
    try {
      if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent)
          || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
        const installed = window.matchMedia('(display-mode: standalone)').matches
          || window.navigator.standalone === true;
        if (isIOS && !installed) {
          msg('devmsg', 'iPhone and iPad only allow notifications for '
            + 'installed web apps: open this page in Safari, tap Share, '
            + 'choose "Add to Home Screen", then open CommuteScout from your '
            + 'Home Screen and tap this button again.', 'err');
        } else {
          msg('devmsg', 'This browser does not support push notifications.', 'err');
        }
        return;
      }
      if (!CFG.vapidPublicKey) {
        msg('devmsg', 'Push is not configured on the server yet.', 'err');
        return;
      }
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') {
        msg('devmsg', 'Notifications were not allowed.', 'err'); return;
      }
      const reg = await navigator.serviceWorker.register('/sw.js');
      await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: b64ToBytes(CFG.vapidPublicKey),
      });
      await api('/api/watch/push', { method: 'POST',
        body: JSON.stringify({ subscription: sub.toJSON() }) });
      msg('devmsg', 'This device will now receive alerts.', 'ok');
    } catch (e) { msg('devmsg', e.message, 'err'); }
  });

  $('deleteacct').addEventListener('click', async () => {
    if (!confirm('Delete your account and all watch areas? This cannot be undone.')) return;
    if (!confirm('Last check: every watch area, alert, and device registration will be removed immediately. Delete?')) return;
    try {
      const r = await api('/api/watch/account', { method: 'DELETE' });
      msg('acctmsg', 'Deleted (' + r.watches + ' watches, ' + r.devices +
        ' devices). Signing out\u2026', 'ok');
      setTimeout(() => signOut(auth), 1400);
    } catch (e) { msg('acctmsg', e.message, 'err'); }
  });

  $('testbtn').addEventListener('click', async () => {
    try {
      const r = await api('/api/watch/test', { method: 'POST' });
      msg('devmsg', 'Test sent to ' + r.devices + ' device(s).', 'ok');
    } catch (e) { msg('devmsg', e.message, 'err'); }
  });

  setVisible(opts.visible !== false);
  return { setVisible, refresh, reloadWatches, watchHere };
}
