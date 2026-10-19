// Offline support: cache the app shell, and keep the last good API answers so the
// demo still opens if the venue Wi-Fi drops.
const CACHE = "sarthi-v1";
const SHELL = ["/", "/assets/app.js", "/assets/app.css", "/manifest.webmanifest", "/icon.svg",
  "/Poppins-Regular.ttf", "/Poppins-Medium.ttf", "/Poppins-Bold.ttf"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/api/")) {
    // network first, fall back to the cached copy
    e.respondWith(fetch(e.request).then((r) => {
      const copy = r.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy));
      return r;
    }).catch(() => caches.match(e.request)));
    return;
  }
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).catch(() => caches.match("/"))));
});
