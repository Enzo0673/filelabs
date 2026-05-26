const CACHE_NAME = 'compressit-v5';
const STATIC_ASSETS = [
  '/',
  '/static/style.css',
  '/static/app.js',
  '/static/tool.js',
  '/static/pdf-preview.js',
  '/static/utils.js',
  '/static/banner.js',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/vendor/pdf.min.js',
  '/static/vendor/pdf.worker.min.js',
  '/tool/compress-pdf',
  '/tool/merge-pdf',
  '/tool/split-pdf',
  '/tool/pdf-to-jpg',
  '/tool/jpg-to-pdf',
  '/tool/rotate-pdf',
  '/tool/watermark-pdf',
  '/tool/page-numbers-pdf',
  '/tool/delete-pages-pdf',
  '/tool/unlock-pdf',
  '/tool/protect-pdf',
  '/tool/repair-pdf',
  '/tool/compress-image',
  '/tool/resize-image',
  '/tool/convert-image',
  '/tool/crop-image',
  '/tool/rotate-image',
  '/tool/compress-video',
  '/tool/compress-archive',
];

// Installation : mise en cache de tous les assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Activation : suppression des anciens caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch : network-first pour les API, cache-first pour tout le reste
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Toujours réseau pour les routes API (upload/traitement/download)
  if (
    url.pathname.startsWith('/compress') ||
    url.pathname.startsWith('/download') ||
    url.pathname.startsWith('/cleanup') ||
    url.pathname.startsWith('/health') ||
    url.pathname.startsWith('/pdf/') ||
    url.pathname.startsWith('/image/') ||
    url.pathname.startsWith('/video/')
  ) {
    return;
  }

  // Cache-first pour toutes les pages et assets statiques
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(response => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      });
    })
  );
});
