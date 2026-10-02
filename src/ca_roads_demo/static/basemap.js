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
  const STADIA_ATTR = '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>'
    + ' &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a>'
    + ' &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  const FLAVOR = { Positron: 'positron', Bright: 'bright', Slate: 'slate', Gray: 'grayscale', Dark: 'dark' };

  let gl = null;   // null: not tried yet
  function canDrawOwn() {
    if (gl !== null) return gl;
    gl = false;
    try {
      if (!window.maplibregl || !window.pmtiles || !L.maplibreGL) return gl;
      const probe = document.createElement('canvas');
      if (!(probe.getContext('webgl2') || probe.getContext('webgl'))) return gl;
      maplibregl.setWorkerUrl('/static/vendor/maplibre-gl-csp-worker.js');
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
  window.csBaseLayer = function (name) {
    const flavor = FLAVOR[name] || FLAVOR.Positron;
    if (!canDrawOwn()) {
      return L.tileLayer('https://tiles.stadiamaps.com/tiles/'
        + (flavor === 'dark' ? 'alidade_smooth_dark' : 'alidade_smooth') + '/{z}/{x}/{y}{r}.png',
      { keepBuffer: 4, maxZoom: 17, crossOrigin: 'anonymous', attribution: STADIA_ATTR });
    }
    return L.maplibreGL({ style: '/api/map/style.json?flavor=' + flavor, interactive: false });
  };
})();
