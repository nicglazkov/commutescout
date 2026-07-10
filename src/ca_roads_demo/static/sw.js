/* Service worker: receives watch-area push alerts and opens /watch on
   tap. No fetch interception - the page works identically without it. */

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

self.addEventListener('push', (e) => {
  let data = {};
  try { data = e.data ? e.data.json() : {}; } catch (err) { /* text push */ }
  const title = data.title || 'CA Roads alert';
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
