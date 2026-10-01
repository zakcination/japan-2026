/* Offline for the trip guide on GitHub Pages.
   The page is one file, so caching it once makes the whole guide work with no signal.
   Page: network first (so updates arrive), cache when offline.
   Trips (trips/*.json): network first, last good copy when offline.
   Weather: network first, last good answer when offline. Everything else: cache first. */
const CACHE = 'japan2026-v2', BADGE = 'japan2026-badge';
const CORE = ['./', 'index.html', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE && k !== BADGE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
const networkFirst = req => fetch(req).then(res => {
  if (res && res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
  return res;
}).catch(() => caches.match(req, { ignoreSearch: false }).then(r => r || caches.match('index.html')));

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (req.mode === 'navigate') { e.respondWith(networkFirst(req)); return; }
  if (url.origin === location.origin && /\/trips\/[a-z0-9-]+\.json$/.test(url.pathname)) {
    e.respondWith(fetch(req).then(res => {
      if (res && res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(url.pathname, copy)); }
      return res;
    }).catch(() => caches.match(url.pathname).then(r => r || new Response('', { status: 504 }))));
    return;
  }
  if (/open-meteo\.com$/.test(url.hostname)) {
    e.respondWith(fetch(req).then(res => {
      if (res && res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    }).catch(() => caches.match(req)));
    return;
  }
  if (url.origin === location.origin) {
    e.respondWith(caches.match(req).then(r => r || networkFirst(req)));
  }
});

/* Web Push (group plan): show it, count it on the icon, open the app where it points.
   The badge counts notifications not yet seen; the app clears it when opened. */
const badgeAdd = async d => {
  const c = await caches.open(BADGE), r = await c.match('n');
  const n = Math.max(0, (r ? +(await r.text()) : 0) + d);
  await c.put('n', new Response(String(n)));
  return n;
};
self.addEventListener('push', e => {
  let m = {}; try { m = e.data ? e.data.json() : {}; } catch (x) { m = { title: e.data ? e.data.text() : '' }; }
  e.waitUntil((async () => {
    const n = await badgeAdd(1);
    if (self.navigator && self.navigator.setAppBadge) self.navigator.setAppBadge(n).catch(() => {});
    await self.registration.showNotification(m.title || 'Поездка', { body: m.body || '', tag: m.tag, data: { url: m.url || './' }, icon: 'icon-192.png', badge: 'icon-192.png' });
  })());
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || './', self.location.href);
  if (url.origin !== self.location.origin) return;                          // only our own pages
  e.waitUntil((async () => {
    const all = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const w = all.find(c => new URL(c.url).origin === url.origin);
    if (w) { await w.focus(); return w.navigate(url.href).catch(() => {}); }
    return self.clients.openWindow(url.href);
  })());
});
self.addEventListener('message', e => {                                     // the app was opened: the badge is seen
  if (e.data === 'badge:clear') e.waitUntil(caches.open(BADGE).then(c => c.put('n', new Response('0'))));
});
