const SHELL_CACHE = 'hospital-shell-v2'

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(['/', '/manifest.webmanifest', '/icon.svg'])),
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== SHELL_CACHE).map((key) => caches.delete(key))),
    ).then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return

  const requestUrl = new URL(event.request.url)
  if (requestUrl.origin !== self.location.origin || requestUrl.pathname.startsWith('/api')) {
    return
  }

  const isShellRequest =
    event.request.mode === 'navigate' ||
    requestUrl.pathname === '/' ||
    requestUrl.pathname.endsWith('.html') ||
    requestUrl.pathname === '/manifest.webmanifest' ||
    requestUrl.pathname === '/sw.js'

  if (isShellRequest) {
    event.respondWith(
      fetch(event.request)
        .then((networkResponse) => {
          const clonedResponse = networkResponse.clone()
          caches.open(SHELL_CACHE).then((cache) => cache.put(event.request, clonedResponse))
          return networkResponse
        })
        .catch(() => caches.match(event.request).then((cachedResponse) => cachedResponse || caches.match('/'))),
    )
    return
  }

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) return cachedResponse

      return fetch(event.request).then((networkResponse) => {
        const clonedResponse = networkResponse.clone()
        caches.open(SHELL_CACHE).then((cache) => cache.put(event.request, clonedResponse))
        return networkResponse
      })
    }),
  )
})
