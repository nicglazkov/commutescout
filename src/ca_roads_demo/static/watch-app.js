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

  // ------------------------------------------------------------- sign-in

  $('googlebtn').addEventListener('click', async () => {
    try { await signInWithPopup(auth, new GoogleAuthProvider()); }
    catch (e) { msg('signinmsg', e.message, 'err'); }
  });

  $('emailbtn').addEventListener('click', async () => {
    const email = $('email').value.trim();
    if (!email) { msg('signinmsg', 'Enter your email first.', 'err'); return; }
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
    if (me.status === 'approved') {
      show('appzone');
      if (CFG.emailEnabled) $('emailchan').classList.remove('hidden');
      renderWatches();
      setTimeout(() => map.invalidateSize(), 60);
    } else {
      $('gatetext').textContent = me.status === 'revoked'
        ? 'Access for this account has been turned off. Enter a new access code to re-enable it.'
        : 'Watch areas are in a limited trial. Enter an access code to unlock them.';
      show('gate');
    }
  }

  onAuthStateChanged(auth, async (u) => {
    user = u;
    if (!u) { $('who').innerHTML = ''; show('signin'); return; }
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
  const savedLayer = L.layerGroup();
  let visible = false;
  function setVisible(on) {
    on = !!on;
    if (on === visible) return;
    visible = on;
    for (const l of [savedLayer, drawLayer, handleLayer]) {
      if (on) l.addTo(map); else map.removeLayer(l);
    }
    if (on && !fittedOnce) fitSaved();
  }

  let mode = 'circle';
  let center = null;
  let polyPoints = [];
  let polyRef = null;
  let editingShape = null;
  const MAX_PTS = 20;

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
    polygon: 'Tap the map to add corners (3-20). Drag a corner to move it, '
      + 'tap it to remove it, tap a faint dot between corners to add one there.',
    route: 'Name both ends, preview the route, set how far from it you '
      + 'want alerts, then create.',
  };
  let routePts = null;
  let routeLine = null;

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
      L.circle(center, { radius: Number($('radius').value) * 1000,
        color: '#2f81f7', weight: 2, fillColor: '#2f81f7', fillOpacity: 0.12 })
        .addTo(drawLayer);
    }
    if (mode === 'polygon' && polyPoints.length > 1) {
      polyRef = L.polygon(polyPoints, { color: '#2f81f7', weight: 2,
        fillColor: '#2f81f7', fillOpacity: 0.12 }).addTo(drawLayer);
    }
    rebuildHandles();
    $('polytools').classList.toggle('hidden',
      mode !== 'polygon' || !polyPoints.length);
  }

  map.on('click', (e) => {
    if (!active()) return;
    const p = [e.latlng.lat, e.latlng.lng];
    if (!insideCoverage(p[0], p[1])) {
      msg('createmsg', 'Watches stay inside a covered state (offshore California is fine).', 'err');
      return;
    }
    msg('createmsg', '');
    if (mode === 'circle') center = p;
    else if (polyPoints.length < MAX_PTS) polyPoints.push(p);
    redraw();
  });

  $('undopt').addEventListener('click', () => {
    polyPoints.pop(); redraw();
  });
  $('clearpts').addEventListener('click', () => {
    polyPoints = []; redraw();
  });

  function startShapeEdit(w) {
    editingShape = { id: w.id, name: w.name };
    mode = 'polygon';
    $('mode-circle').classList.remove('on');
    $('mode-polygon').classList.add('on');
    $('radiusrow').classList.add('hidden');
    center = null;
    polyPoints = (w.points || []).map(
      (pt) => Array.isArray(pt) ? pt.slice() : [pt.lat, pt.lon]);
    $('shapehint').textContent = 'Editing the shape of \u201c' + w.name
      + '\u201d. Drag corners, tap one to remove it, tap a faint dot to '
      + 'add one, tap the map to append at the end.';
    $('createbtn').textContent = 'Save shape';
    $('canceledit').classList.remove('hidden');
    redraw();
    if (polyPoints.length > 1) {
      map.fitBounds(L.polygon(polyPoints).getBounds().pad(0.4));
    }
    if ($('wmap')) $('wmap').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function endShapeEdit() {
    editingShape = null;
    $('createbtn').textContent = 'Create watch';
    $('canceledit').classList.add('hidden');
    setMode('circle');
  }

  $('canceledit').addEventListener('click', endShapeEdit);

  function setMode(m) {
    if (editingShape) {
      editingShape = null;
      $('createbtn').textContent = 'Create watch';
      $('canceledit').classList.add('hidden');
    }
    mode = m;
    $('mode-circle').classList.toggle('on', m === 'circle');
    $('mode-polygon').classList.toggle('on', m === 'polygon');
    $('mode-route').classList.toggle('on', m === 'route');
    $('radiusrow').classList.toggle('hidden', m !== 'circle');
    $('routerow').classList.toggle('hidden', m !== 'route');
    $('shapehint').textContent = HINTS[m];
    center = null; polyPoints = []; routePts = null;
    if (routeLine) { map.removeLayer(routeLine); routeLine = null; }
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
    if (!c) throw new Error('could not find \u201c' + q + '\u201d');
    return c;
  }

  $('rw-preview').addEventListener('click', async () => {
    const fromQ = $('rw-from').value.trim();
    const toQ = $('rw-to').value.trim();
    if (!fromQ || !toQ) {
      msg('createmsg', 'Give the route a start and an end.', 'err');
      return;
    }
    msg('createmsg', 'Routing\u2026');
    try {
      const [a, b] = await Promise.all([geocodeOne(fromQ), geocodeOne(toQ)]);
      const res = await fetch('https://api.stadiamaps.com/route/v1', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          locations: [{ lat: a.lat, lon: a.lon }, { lat: b.lat, lon: b.lon }],
          costing: 'auto',
        }),
      });
      if (!res.ok) throw new Error('routing service unavailable, try again');
      const trip = (await res.json()).trip;
      if (!trip || !trip.legs || !trip.legs.length) {
        throw new Error('no drivable route found');
      }
      routePts = trip.legs.flatMap((l) => decodePolyline6(l.shape));
      if (routeLine) map.removeLayer(routeLine);
      routeLine = L.polyline(routePts, { color: '#2f81f7', weight: 4,
        opacity: 0.8 }).addTo(map);
      map.fitBounds(routeLine.getBounds().pad(0.25));
      if (!$('wname').value.trim()) {
        $('wname').value = (fromQ + ' \u2192 ' + toQ).slice(0, 60);
      }
      msg('createmsg', 'Route previewed - alerts will cover '
        + $('rw-buffer').value + ' mi either side.', 'ok');
    } catch (e) { msg('createmsg', e.message, 'err'); }
  });

  $('rw-buffer').addEventListener('input', () => {
    $('rw-bufferlabel').textContent = $('rw-buffer').value + ' mi';
  });
  $('mode-circle').addEventListener('click', () => setMode('circle'));
  $('mode-polygon').addEventListener('click', () => setMode('polygon'));
  $('radius').addEventListener('input', () => {
    $('radiuslabel').textContent = $('radius').value + ' km';
    redraw();
  });

  // ------------------------------------------------------------- watches

  async function reloadWatches() {
    me = await api('/api/watch/me');
    renderWatches();
  }

  function watchEditor(w) {
    const form = document.createElement('div');
    form.className = 'weditor';
    const nameIn = document.createElement('input');
    nameIn.type = 'text'; nameIn.maxLength = 60; nameIn.value = w.name || '';
    const kindsBox = document.createElement('div');
    kindsBox.className = 'kinds';
    for (const [kind, label] of [['incident', 'Incidents'],
        ['closure', 'Closures'], ['chain', 'Chain controls'],
        ['fire', 'Wildfires']]) {
      const lab = document.createElement('label');
      const cb = document.createElement('input');
      cb.type = 'checkbox'; cb.dataset.kind = kind;
      cb.checked = (w.kinds || []).includes(kind);
      lab.append(cb, document.createTextNode(label));
      kindsBox.append(lab);
    }
    const chanBox = document.createElement('div');
    chanBox.className = 'chans';
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
    save.className = 'primary'; save.textContent = 'Save';
    save.style.width = 'auto'; save.style.padding = '7px 16px';
    const cancel = document.createElement('button');
    cancel.className = 'ghost'; cancel.textContent = 'Cancel';
    const errBox = document.createElement('div');
    errBox.className = 'msg';
    save.addEventListener('click', async (e) => {
      e.stopPropagation();
      const kinds = [...kindsBox.querySelectorAll('input:checked')]
        .map((c) => c.dataset.kind);
      const channels = {};
      for (const cb of chanBox.querySelectorAll('input[data-chan]')) {
        channels[cb.dataset.chan] = cb.checked;
      }
      try {
        await api('/api/watch/' + w.id, { method: 'PATCH',
          body: JSON.stringify({ name: nameIn.value, kinds, channels }) });
        await reloadWatches();
      } catch (err) { msg('listmsg', err.message, 'err'); }
    });
    cancel.addEventListener('click', (e) => { e.stopPropagation(); form.remove(); });
    form.addEventListener('click', (e) => e.stopPropagation());
    const btnRow = document.createElement('div');
    btnRow.className = 'devrow';
    btnRow.append(save, cancel);
    if (w.type === 'polygon') {
      const shapeBtn = document.createElement('button');
      shapeBtn.className = 'ghost';
      shapeBtn.textContent = 'Edit shape on map';
      shapeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        form.remove();
        startShapeEdit(w);
      });
      btnRow.append(shapeBtn);
    }
    form.append(nameIn, kindsBox, chanBox, btnRow, errBox);
    return form;
  }

  function renderWatches() {
    const list = $('wlist');
    list.innerHTML = '';
    savedLayer.clearLayers();
    const used = me.watches.length;
    const cap = CFG.limits.free_watches;
    $('wcount').textContent = used + ' of ' + cap + ' watch areas used';
    $('usagefill').style.width = (cap ? Math.min(100, (used / cap) * 100) : 0) + '%';
    if (!me.watches.length) {
      list.innerHTML = '<div class="empty"><div class="empty-ico"></div>'
        + '<div class="empty-title">No watch areas yet</div>'
        + '<div class="empty-sub">Pick a shape above, draw it on the map, '
        + 'then give it a name to start getting alerts.</div></div>';
      return;
    }
    for (const w of me.watches) {
      const paused = w.active === false;
      const style = paused
        ? { color: '#8a94a3', weight: 1.5, dashArray: '6 6',
            fillColor: '#8a94a3', fillOpacity: 0.05 }
        : { color: '#1c3a2e', weight: 1.5,
            fillColor: '#1c3a2e', fillOpacity: 0.08 };
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
      dot.style.background = paused ? '#8a94a3' : '#1c3a2e';
      const text = document.createElement('div');
      const name = document.createElement('div');
      name.className = 'wname';
      name.textContent = w.name + (paused ? ' (paused)' : '');
      const meta = document.createElement('div');
      meta.className = 'wmeta';
      const chans = [];
      if ((w.channels || {}).push !== false) chans.push('push');
      if ((w.channels || {}).email) chans.push('email');
      meta.textContent = (w.type === 'circle'
        ? Math.round(w.radius_km) + ' km circle'
        : w.type === 'route'
          ? Math.round((w.length_km || 0) * 0.6214) + ' mi route \u00b7 '
            + Math.round((w.buffer_km || 3) * 0.6214) + ' mi buffer'
          : 'polygon') +
        ' - ' + (w.kinds || []).join(', ') +
        ' - ' + (chans.join(' + ') || 'no delivery');
      text.append(name, meta);
      const pause = document.createElement('button');
      pause.textContent = paused ? '\u25b6' : '\u23f8';
      pause.title = paused ? 'Resume alerts' : 'Pause alerts';
      pause.addEventListener('click', async (e) => {
        e.stopPropagation();
        try {
          await api('/api/watch/' + w.id, { method: 'PATCH',
            body: JSON.stringify({ active: paused }) });
          await reloadWatches();
        } catch (err) { msg('listmsg', err.message, 'err'); }
      });
      const edit = document.createElement('button');
      edit.textContent = '\u270e';
      edit.title = 'Edit name, kinds, delivery';
      edit.addEventListener('click', (e) => {
        e.stopPropagation();
        const open = row.querySelector('.weditor');
        if (open) { open.remove(); return; }
        row.append(watchEditor(w));
      });
      const del = document.createElement('button');
      del.textContent = '\u00d7';
      del.title = 'Delete watch';
      del.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (!confirm('Delete "' + w.name + '"? Alerts for this area stop immediately.')) return;
        try {
          await api('/api/watch/' + w.id, { method: 'DELETE' });
          await reloadWatches();
        } catch (err) { msg('listmsg', err.message, 'err'); }
      });
      row.append(dot, text, pause, edit, del);
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

  $('createbtn').addEventListener('click', async () => {
    if (editingShape) {
      if (polyPoints.length < 3) {
        msg('createmsg', 'A shape needs at least three corners.', 'err');
        return;
      }
      try {
        await api('/api/watch/' + editingShape.id, { method: 'PATCH',
          body: JSON.stringify({ points: polyPoints }) });
        endShapeEdit();
        await reloadWatches();
        msg('createmsg', 'Shape updated.', 'ok');
      } catch (e) { msg('createmsg', e.message, 'err'); }
      return;
    }
    const kinds = [...document.querySelectorAll('.kinds input:checked')]
      .map((c) => c.dataset.kind);
    const body = {
      name: $('wname').value.trim(),
      kinds,
      channels: { push: $('ch-push').checked, email: $('ch-email').checked },
    };
    if (mode === 'circle') {
      if (!center) { msg('createmsg', 'Click the map to place the center first.', 'err'); return; }
      Object.assign(body, { type: 'circle',
        center: { lat: center[0], lon: center[1] },
        radius_km: Number($('radius').value) });
    } else if (mode === 'route') {
      if (!routePts || routePts.length < 2) {
        msg('createmsg', 'Preview the route first.', 'err'); return;
      }
      Object.assign(body, { type: 'route', points: routePts,
        // 1.6, not the more precise 1.609: at the 2 mi slider max this
        // lands buffer_km exactly on the 3.2 km free cap instead of
        // just over it, so the top of the slider never gets rejected.
        buffer_km: Number($('rw-buffer').value) * 1.6 });
    } else {
      if (polyPoints.length < 3) { msg('createmsg', 'Add at least three corners on the map.', 'err'); return; }
      Object.assign(body, { type: 'polygon', points: polyPoints });
    }
    try {
      await api('/api/watch/create', { method: 'POST',
        body: JSON.stringify(body) });
      center = null; polyPoints = []; routePts = null;
      if (routeLine) { map.removeLayer(routeLine); routeLine = null; }
      $('wname').value = ''; $('rw-from').value = ''; $('rw-to').value = '';
      redraw();
      me = await api('/api/watch/me');
      renderWatches();
      msg('createmsg', 'Watch created.', 'ok');
    } catch (e) { msg('createmsg', e.message, 'err'); }
  });

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
  return { setVisible, refresh, reloadWatches };
}
