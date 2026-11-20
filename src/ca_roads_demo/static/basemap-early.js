/* Runs from the head, before a megabyte of map code has been parsed:
 * asks for the base map's style now, so the map library finds it already
 * here. Which style depends on the saved choice. The names match
 * basemap.js. Kept in a file of its own because the page carries no
 * inline script.
 *
 * It also sets the colour theme before first paint, the same way the
 * site does (site/app/layout.tsx): the saved "cs-theme" choice, else the
 * system setting. With no saved base map, a dark page starts on the Dark
 * base map so the first frame does not flash a white map. */
(function () {
  var root = document.documentElement;
  var theme = null;
  try { theme = localStorage.getItem('cs-theme'); } catch (e) { /* private mode */ }
  if (theme !== 'light' && theme !== 'dark') {
    theme = (window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
  }
  root.dataset.theme = theme;
  var flavor = { Positron: 'positron', Bright: 'bright', Slate: 'slate', Gray: 'grayscale', Dark: 'dark' };
  var name = null;
  try { name = localStorage.getItem('cs-basemap'); } catch (e) { /* private mode */ }
  if (!flavor[name]) name = theme === 'dark' ? 'Dark' : 'Positron';
  var link = document.createElement('link');
  link.rel = 'preload'; link.as = 'fetch'; link.crossOrigin = 'anonymous';
  link.href = '/api/map/style.json?flavor=' + flavor[name];
  document.head.appendChild(link);
})();
