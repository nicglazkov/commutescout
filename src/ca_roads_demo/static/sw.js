/* Service worker: receives watch-area push alerts and opens /watch on
   tap. No fetch interception - the page works identically without it. */

const ASSET_CACHE = 'ca-roads-assets-v2';

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
    if (key.startsWith('ca-roads-assets-') && key !== ASSET_CACHE) {
      await caches.delete(key);
    }
  }
  await self.clients.claim();
})()));

// Cache-first for vendored assets only: Leaflet, fonts, icons. Pages
// and API calls always hit the network, so deploys stay instant.
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
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
