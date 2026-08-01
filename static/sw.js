/* Prism PWA app-shell cache. Authenticated /api data is deliberately excluded. */
const CACHE_VERSION = 'prism-shell-20260802-v2';
const scopeUrl = new URL(self.registration.scope);
const scopePath = scopeUrl.pathname.replace(/\/$/, '');
const atScope = (path) => new URL(scopePath + path, self.location.origin).toString();

const SHELL_ASSETS = [
  '/app',
  '/manifest.webmanifest',
  '/static/vendor/xterm/xterm.css',
  '/static/vendor/cropper.min.css',
  '/static/vendor/hljs/highlight.min.js',
  '/static/vendor/hljs/python.min.js',
  '/static/vendor/hljs/javascript.min.js',
  '/static/vendor/hljs/typescript.min.js',
  '/static/vendor/hljs/bash.min.js',
  '/static/vendor/hljs/json.min.js',
  '/static/vendor/hljs/markdown.min.js',
  '/static/vendor/hljs/css.min.js',
  '/static/vendor/hljs/xml.min.js',
  '/static/vendor/xterm/xterm.js',
  '/static/vendor/cropper.min.js',
  '/static/vendor/xterm/addon-fit.js',
  '/static/vendor/xterm/xterm-addon-web-links.js',
  '/static/vendor/xterm/addon-unicode-graphemes.js',
  '/static/chat-md.js',
  '/static/chat-code.js',
  '/static/chat-page.js',
  '/static/icons/prism-192.png',
  '/static/icons/prism-512.png',
  '/static/icons/prism-maskable-512.png'
].map(atScope);

async function putSafe(cache, request, response) {
  if (response && response.ok && response.type !== 'opaque') {
    await cache.put(request, response.clone());
  }
  return response;
}

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_VERSION);
    await Promise.allSettled(SHELL_ASSETS.map(async (url) => {
      const response = await fetch(url, { cache: 'reload', credentials: 'same-origin' });
      await putSafe(cache, url, response);
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys
      .filter((key) => key.startsWith('prism-shell-') && key !== CACHE_VERSION)
      .map((key) => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  const apiPrefix = scopePath + '/api/';
  if (url.pathname.startsWith(apiPrefix)) {
    // Terminal streams, messages, uploads, auth and tokens are network-only.
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_VERSION);
      const cached = await cache.match(request, { ignoreSearch: true })
        || await cache.match(atScope('/app'));
      const network = fetch(request).then(async (response) => {
        await putSafe(cache, request, response);
        await putSafe(cache, atScope('/app'), response);
        return response;
      });
      if (cached) {
        event.waitUntil(network.catch(() => undefined));
        return cached;
      }
      try {
        return await network;
      } catch (_) {
        return new Response('Prism is offline. Reconnect once to finish installation.', {
          status: 503,
          headers: { 'Content-Type': 'text/plain; charset=utf-8' }
        });
      }
    })());
    return;
  }

  const isShellAsset = url.pathname.startsWith(scopePath + '/static/')
    || url.pathname === scopePath + '/manifest.webmanifest';
  if (!isShellAsset) return;

  event.respondWith((async () => {
    const cache = await caches.open(CACHE_VERSION);
    const cached = await cache.match(request, { ignoreSearch: true });
    const network = fetch(request).then((response) => putSafe(cache, request, response));
    if (cached) {
      event.waitUntil(network.catch(() => undefined));
      return cached;
    }
    return network;
  })());
});
