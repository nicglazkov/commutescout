/* Runs from the head, before a megabyte of map code has been parsed:
 * asks for the base map's style now, so the map library finds it already
 * here. Which style depends on the saved choice. The names match
 * basemap.js. Kept in a file of its own because the page carries no
 * inline script. */
(function () {
  var flavor = { Positron: 'positron', Bright: 'bright', Slate: 'slate', Gray: 'grayscale', Dark: 'dark' };
  var name = null;
  try { name = localStorage.getItem('cs-basemap'); } catch (e) { /* private mode */ }
  var link = document.createElement('link');
  link.rel = 'preload'; link.as = 'fetch'; link.crossOrigin = 'anonymous';
  link.href = '/api/map/style.json?flavor=' + (flavor[name] || 'positron');
  document.head.appendChild(link);
})();
