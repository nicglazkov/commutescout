/* The base map under every Leaflet map on the site.
 *
 * Five styles, drawn by MapLibre mounted inside Leaflet so markers,
 * popups and panes work as before. The server hands out each style
 * (/api/map/style.json?flavor=...), so the site and the apps always
 * draw the same thing:
 *
 *   Positron, Bright   OpenFreeMap's styles (OpenMapTiles layout)
 *   Slate, Gray, Dark  themes over our own map file (Protomaps layout)
 *
 * A browser with no WebGL gets Stadia's raster tiles instead.
 *
 * CS_BASEMAPS lists the names in menu order, csBaseLayer(name) returns
 * a Leaflet layer, and csBasemapThumb(name) is a small picture of the
 * style for the picker.
 */
(function () {
  const FLAVOR = { Positron: 'positron', Bright: 'bright', Slate: 'slate', Gray: 'grayscale', Dark: 'dark' };

  // The worker is fetched under a fresh address on every deploy. A
  // worker obeys the security policy that came with ITS OWN file, and
  // vendor files are cached for a week by the browser, the service
  // worker and the CDN: under a fixed address, a policy change (a new
  // tile host) reached the page at once and the worker a week later,
  // and the map drew nothing in between. The page's asset version rides
  // on this script's own address; a page without one uses the fallback.
  const REV = (function () {
    try { return new URL(document.currentScript.src).searchParams.get('v') || 'w2'; } catch (e) { return 'w2'; }
  })();
  // How long the base map takes, for anyone measuring (performance
  // marks basemap-start and basemap-ready).
  function mark(name) { try { performance.mark(name); } catch (e) { /* no marks */ } }

  let gl = null;   // null: not tried yet
  function canDrawOwn() {
    if (gl !== null) return gl;
    gl = false;
    try {
      if (!window.maplibregl || !window.pmtiles || !L.maplibreGL) return gl;
      const probe = document.createElement('canvas');
      if (!(probe.getContext('webgl2') || probe.getContext('webgl'))) return gl;
      maplibregl.setWorkerUrl('/static/vendor/maplibre-gl-csp-worker.js?v=' + REV);
      maplibregl.addProtocol('pmtiles', new pmtiles.Protocol().tile);
      gl = true;
    } catch (e) { gl = false; }
    return gl;
  }

  window.CS_BASEMAPS = Object.keys(FLAVOR);
  window.CS_BASEMAP_DEFAULT = 'Positron';
  window.csBasemapThumb = function (name) {
    return '/static/mapstyle/thumbs/' + (FLAVOR[name] || FLAVOR.Positron) + '.webp';
  };
  window.csBasemapStyleUrl = function (name) {
    return '/api/map/style.json?flavor=' + (FLAVOR[name] || FLAVOR.Positron);
  };
  window.csBaseLayer = function (name) {
    const flavor = FLAVOR[name] || FLAVOR.Positron;
    if (!canDrawOwn()) {
      // No WebGL (an old browser, a headless fetch): the road data still
      // draws over a blank map, and one line says why. There is no
      // raster fallback any more: it was a paid tile for every bot visit.
      const empty = L.layerGroup();
      empty.on('add', (e) => {
        const box = e.target._map && e.target._map.getContainer();
        if (!box || box.querySelector('.cs-nogl')) return;
        const note = document.createElement('div');
        note.className = 'cs-nogl';
        note.textContent = 'This map needs WebGL, which this browser does not offer. Road data still shows.';
        note.style.cssText = 'position:absolute;left:50%;top:12px;transform:translateX(-50%);'
          + 'z-index:400;max-width:90%;background:#fff;color:#333;padding:6px 10px;'
          + 'border-radius:6px;font:13px system-ui,sans-serif;box-shadow:0 1px 4px rgba(0,0,0,.3)';
        box.appendChild(note);
      });
      return empty;
    }
    mark('basemap-start');
    // No cross-fade: tiles and labels show the moment they are ready,
    // not a third of a second later.
    const layer = L.maplibreGL({ style: csBasemapStyleUrl(name), interactive: false, fadeDuration: 0 });
    layer.once('add', () => {
      const gl = layer.getMaplibreMap && layer.getMaplibreMap();
      if (gl) gl.once('idle', () => mark('basemap-ready'));
    });
    return layer;
  };
})();
