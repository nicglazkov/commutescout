/* The base map under every Leaflet map on the site.
 *
 * It draws from our own map files (one vector archive on
 * data.commutescout.com, the same one the phone apps use) through
 * MapLibre, mounted inside Leaflet so markers, popups and panes work as
 * before. Outdoors and Terrain have hill shading our files do not carry;
 * those two still come from Stadia, as does everything when the browser
 * has no WebGL.
 *
 * csBaseLayer(name) returns a Leaflet layer. CS_BASEMAPS lists the names
 * in menu order.
 */
(function () {
  const STADIA_ATTR = '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>'
    + ' &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a>'
    + ' &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  const STAMEN_ATTR = STADIA_ATTR.replace(' &copy; <a href="https://openmaptiles.org/">',
    ' &copy; <a href="https://stamen.com/">Stamen Design</a> &copy; <a href="https://openmaptiles.org/">');
  const OWN = { Light: 'light', Gray: 'grayscale', Dark: 'dark' };
  const STADIA = {
    Outdoors: ['outdoors', STADIA_ATTR],
    Terrain: ['stamen_terrain', STAMEN_ATTR],
  };

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

  function stadia(style, attr) {
    return L.tileLayer('https://tiles.stadiamaps.com/tiles/' + style + '/{z}/{x}/{y}{r}.png',
      { keepBuffer: 4, maxZoom: 17, crossOrigin: 'anonymous', attribution: attr });
  }

  window.CS_BASEMAPS = Object.keys(OWN).concat(Object.keys(STADIA));
  window.CS_BASEMAP_DEFAULT = 'Light';
  window.csBaseLayer = function (name) {
    if (STADIA[name]) return stadia(STADIA[name][0], STADIA[name][1]);
    const flavor = OWN[name] || OWN.Light;
    if (!canDrawOwn()) return stadia(flavor === 'dark' ? 'alidade_smooth_dark' : 'alidade_smooth', STADIA_ATTR);
    return L.maplibreGL({ style: '/api/map/style.json?flavor=' + flavor, interactive: false });
  };
})();
