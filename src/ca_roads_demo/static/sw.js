/* Service worker: receives watch-area push alerts and opens /watch on
   tap. No fetch interception - the page works identically without it. */

const ASSET_CACHE = 'ca-roads-assets-v2';
const SNAP_CACHE = 'ca-roads-snap-v1';
const SNAP_HOST = 'data.commutescout.com';
// Basemap tiles, cached on-device only (rev 2: the server's CSP now
// lists the tile host in connect-src, which governs fetch() in this
// worker; the byte change here forces installed workers to update and
// pick up that policy). Stadia's terms allow standard
// client-side caching (local to the device, up to the HTTP header or 7
// days) and prohibit server-side caching; this honors their 6h
// max-age and never exceeds it. Bounded so a long pan session cannot
// eat the visitor's disk.
const TILE_CACHE = 'ca-roads-tiles-v1';
const TILE_HOST = 'tiles.stadiamaps.com';
const TILE_FRESH_MS = 6 * 60 * 60 * 1000;
const TILE_MAX_ENTRIES = 800;

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const cache = await caches.open(ASSET_CACHE);
    await cache.addAll([
      '/static/vendor/leaflet.js', '/static/vendor/leaflet.css',
      '/static/fonts/fonts.css',
      '/static/icon-192.png', '/static/icon-512.png',
    ]).catch(() => {});
    await self.skipWaiting();
  })());
});
self.addEventListener('activate', (e) => e.waitUntil((async () => {
  for (const key of await caches.keys()) {
    if ((key.startsWith('ca-roads-assets-') && key !== ASSET_CACHE)
        || (key.startsWith('ca-roads-snap-') && key !== SNAP_CACHE)
        || (key.startsWith('ca-roads-tiles-') && key !== TILE_CACHE)) {
      await caches.delete(key);
    }
  }
  // Stadia's terms cap client retention at 7 days; sweep anything a
  // long-idle device may still hold past that.
  const tiles = await caches.open(TILE_CACHE);
  for (const req of await tiles.keys()) {
    const hit = await tiles.match(req);
    const at = Number(hit && hit.headers.get('sw-fetched-on') || 0);
    if (Date.now() - at > 7 * 24 * 60 * 60 * 1000) await tiles.delete(req);
  }
  await self.clients.claim();
})()));

// Map snapshots. A repeat visit paints the last snapshot from disk with
// no network in the critical path, and the fresh copy lands behind it.
// Stale bytes can never quietly mislead: the page reads the payload's
// own "published" timestamp and shows the "data as of" chip.
//
// Network-first, cache-fallback, and the cache is kept warm on every
// success. The instant paint is NOT done by returning stale bytes here:
// the page reads this same cache itself (caches.match) to paint before
// the network answers, then repaints when this resolves. Doing it that
// way means a poll always sees fresh data, where serving stale from the
// worker would leave every open map one full interval behind.
async function snapshotFirst(request) {
  const cache = await caches.open(SNAP_CACHE);
  try {
    const res = await fetch(request);
    if (res && res.ok) cache.put(request, res.clone());
    return res;
  } catch (e) {
    const hit = await cache.match(request);
    if (hit) return hit;
    throw e;
  }
}

// Tiles: cache-first while fresh, refresh from the network after 6h,
// and fall back to a stale tile when offline (a stale basemap beats a
// gray one; the DATA layers are never cached here, so dots stay live).
async function tileFirst(request) {
  const cache = await caches.open(TILE_CACHE);
  const hit = await cache.match(request);
  if (hit) {
    const at = Number(hit.headers.get('sw-fetched-on') || 0);
    if (Date.now() - at < TILE_FRESH_MS) return hit;
  }
  try {
    const res = await fetch(request);
    if (res && res.ok) {
      const body = await res.clone().arrayBuffer();
      const headers = new Headers(res.headers);
      headers.set('sw-fetched-on', String(Date.now()));
      await cache.put(request, new Response(body, { status: 200, headers }));
      trimTiles(cache); // fire and forget
    }
    return res;
  } catch (err) {
    if (hit) return hit;
    throw err;
  }
}

// Keep the tile cache bounded: drop the oldest entries (insertion
// order) once over the cap. Runs occasionally, not on the hot path.
let tileTrimPending = false;
async function trimTiles(cache) {
  if (tileTrimPending) return;
  tileTrimPending = true;
  try {
    const keys = await cache.keys();
    for (let i = 0; i < keys.length - TILE_MAX_ENTRIES; i++) {
      await cache.delete(keys[i]);
    }
  } finally {
    tileTrimPending = false;
  }
}

// Cache-first for vendored assets only: Leaflet, fonts, icons. Pages
// and API calls always hit the network, so deploys stay instant.
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (url.hostname === TILE_HOST && e.request.method === 'GET') {
    e.respondWith(tileFirst(e.request));
    return;
  }
  if (url.hostname === SNAP_HOST && e.request.method === 'GET') {
    e.respondWith(snapshotFirst(e.request));
    return;
  }
  if (url.origin !== location.origin) return;
  if (!/^\/static\/(vendor|fonts)\/|^\/static\/icon-/.test(url.pathname)) return;
  e.respondWith((async () => {
    const cache = await caches.open(ASSET_CACHE);
    const hit = await cache.match(e.request);
    if (hit) return hit;
    const res = await fetch(e.request);
    if (res.ok) cache.put(e.request, res.clone());
    return res;
  })());
});

self.addEventListener('push', (e) => {
  let data = {};
  try { data = e.data ? e.data.json() : {}; } catch (err) { /* text push */ }
  const title = data.title || 'CommuteScout alert';
  e.waitUntil(self.registration.showNotification(title, {
    body: data.body || '',
    icon: '/static/icon-192.png',
    badge: '/static/icon-192.png',
    tag: data.tag || undefined,
    data: { url: data.url || '/watch' },
  }));
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || '/watch';
  e.waitUntil(self.clients.matchAll({ type: 'window' }).then((tabs) => {
    for (const tab of tabs) {
      if (tab.url.includes('/watch') && 'focus' in tab) return tab.focus();
    }
    return self.clients.openWindow(url);
  }));
});
